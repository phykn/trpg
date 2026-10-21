// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';
import { ScrollView, Text, TextInput } from 'react-native';

import { Dice, Face } from '@/components/game/Dice';
import { RollCard } from '@/components/game/RollCard';
import { motion } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { useGame } from '@/logic/useGame';
import { ApiError, getGame, getStories, sendCommand, stream } from '@/services/api';
import { storeLog } from '@/services/storage';
import type { Card, CommandResult, GameView, NarrationEvent, Preview, StepRecord } from '@/services/types';
import { Play } from '../Play';

jest.mock('@/services/api', () => ({
  ApiError: class extends Error {
    status: number; view: unknown; reason: unknown;
    constructor(status: number, view: unknown, reason: unknown) { super('x'); this.status = status; this.view = view; this.reason = reason; }
  },
  getStories: jest.fn(), getGame: jest.fn(), sendCommand: jest.fn(), createGame: jest.fn(), stream: jest.fn(),
  narrationPath: (id: string, n: number) => `/n/${id}/${n}`, recapPath: (id: string, k: number) => `/r/${id}/${k}`,
}));
jest.mock('@/services/storage', () => ({
  loadGameId: jest.fn(() => 'g_1'), storeGameId: jest.fn(() => true), clearGameId: jest.fn(),
  loadLog: jest.fn(() => []), storeLog: jest.fn(),
}));

const TEXT = '바람이 붑니다.';
const base: GameView = {
  revision: 0, story: { id: 's', title: 'S', premise: '등대가 꺼졌습니다.' }, chapter: { k: 1, title: 'C', aim: 'A' },
  scene: { place: { id: 'dock', name: '선착장', senses: [] }, people: [], things: [], obstacles: [], exits: [], tags: [] },
  player: { name: 'N', approaches: [], traits: [], tags: [], things: [], wounds: 0, wound_boxes: 2, beats: 0, beats_max: 6, growth: 0 },
  clocks: [], journal: { beliefs: [], owes: [], relations: [], choices: [] },
  buttons: [], growth: [], card: null, last: null, recaps: [], ending: null,
};
const walk: StepRecord = {
  t: 0, action: 'look', label: 'Look', result: 'none', risk: 'low', dc: null, roll: null, mods: [], total: null, decisive: [], changes: [],
};
const told: GameView = { ...base, revision: 1, last: { turn: 1, steps: [walk], narrated: true } };

type Node = { props: Record<string, unknown> };
let tree: ReturnType<typeof renderer.create> | undefined;
let game: ReturnType<typeof useGame>;
function Screen() { game = useGame(); return game.view ? <Play game={game} /> : null; }

const input = () => tree!.root.findAllByType(TextInput)[0];
const pressable = (label: string) => tree!.root.findAll((n: Node) => n.props.accessibilityLabel === label && typeof n.props.onPress === 'function')[0];
const screenText = () => JSON.stringify(tree!.toJSON());
const chat = () => tree!.root.findByType(ScrollView).findAllByType(Text)
  .map((t: { props: { children: unknown } }) => [t.props.children].flat(3).join('')).join('|');
async function say(text: string) {
  await flush(async () => { input().props.onChangeText(text); });
  await flush(async () => { input().props.onSubmitEditing(); });
}

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  (getStories as jest.Mock).mockResolvedValue([]);
  (stream as jest.Mock).mockImplementation(async (_p: string, on: (e: NarrationEvent) => void) => {
    on({ type: 'text', text: TEXT });
    on({ type: 'done', tags: [] });
  });
});
afterEach(async () => { await flush(async () => { tree?.unmount(); }); jest.useRealTimers(); });

test('while the narration is typed, the input is locked and a sentence goes nowhere', async () => {
  (getGame as jest.Mock).mockResolvedValue(told);
  await flush(async () => { tree = renderer.create(<Screen />); });
  expect(game.phase).toBe('narrating');
  expect(input().props.editable).toBe(false);
  await say('문을 연다');
  expect(sendCommand).not.toHaveBeenCalled();
  expect(chat()).not.toContain('문을 연다');
  await flush(async () => { jest.advanceTimersByTime((1000 / motion.typeRate) * (TEXT.length + 2)); });
  expect(game.phase).toBe('idle');
  expect(input().props.editable).toBe(true);
});

test('a lost answer leaves only the resend, which sends the identical command', async () => {
  (getGame as jest.Mock).mockResolvedValue(base);
  const result: CommandResult = { kind: 'refused', turn: null, steps: [], reason: '여기서는 할 수 없습니다.', view: base };
  (sendCommand as jest.Mock).mockReturnValueOnce(new Promise(() => undefined)).mockResolvedValueOnce(result);
  await flush(async () => { tree = renderer.create(<Screen />); });
  await say('문을 연다');
  expect(chat()).toContain('문을 연다');
  await flush(async () => { jest.advanceTimersByTime(motion.stuck); });
  expect(tree!.root.findAllByType(TextInput)).toHaveLength(0);
  expect(screenText()).toContain(ko.stuck);
  await flush(async () => { (pressable(ko.resend).props.onPress as () => void)(); });
  const [first, second] = (sendCommand as jest.Mock).mock.calls;
  expect(second).toEqual(first);
  expect(input().props.editable).toBe(true);
  expect(screenText()).toContain('여기서는 할 수 없습니다.');
});

const preview = (help: number): Preview => ({
  risk: 'normal', z: 2, dc: 8, stakes: { clock: 1, weight: 'light' }, clock: null, gain: { kind: 'fill', boxes: 1, fit: 0 },
  mods: [{ kind: 'stat', label: '솜씨', value: 2 }, ...(help ? [{ kind: 'help' as const, label: '열쇠', value: help }] : [])],
});
const door: Card = {
  id: 'c1', kind: 'roll', echo: { text: '문을 연다', slots: [] }, selected: null,
  plan: { step: { action: 'try:door:finesse', label: '문을 연다', target: { id: 'door', name: '문', fill: 0, boxes: 1 } }, rest: [] },
  options: [
    { id: 'try:door:finesse;rely=thing:key', label: '열쇠', consumed: false, note: null, preview: preview(1) },
    { id: 'try:door:finesse', label: 'none', consumed: false, note: null, preview: preview(0) },
  ],
};
const radio = () => tree!.root.findAll((n: Node) => n.props.accessibilityRole === 'radio' && typeof n.props.onPress === 'function')[0];

test('a lost roll keeps its card with the dice at rest and the resend on it, which rolls the same pick again', async () => {
  (getGame as jest.Mock).mockResolvedValue({ ...base, card: door });
  (sendCommand as jest.Mock).mockReturnValue(new Promise(() => undefined));
  await flush(async () => { tree = renderer.create(<Screen />); });
  await flush(async () => { (radio().props.onPress as () => void)(); });
  await flush(async () => { (pressable(ko.hold).props.onPress as () => void)(); });
  expect(game.phase).toBe('rolling');
  await flush(async () => { jest.advanceTimersByTime(motion.stuck); });
  expect(game.phase).toBe('stuck');
  expect(tree!.root.findAllByType(RollCard)).toHaveLength(1);
  expect(tree!.root.findByType(Dice).props.state).toBe('stopped');
  expect(tree!.root.findByType(Dice).findAllByType(Face).map((f: Node) => f.props.value)).toEqual([0, 0]);
  expect(radio().props.accessibilityState).toMatchObject({ checked: true, disabled: true });
  expect(screenText().split(ko.stuck)).toHaveLength(2);            // once, on the card; the bar under the scrim has none
  await flush(async () => { (pressable(ko.resend).props.onPress as () => void)(); });
  const [first, second] = (sendCommand as jest.Mock).mock.calls;
  expect(second).toEqual(first);
  expect(first[3]).toEqual({ card: 'c1', pick: 'try:door:finesse;rely=thing:key' });
  expect(game.phase).toBe('rolling');
  expect(tree!.root.findByType(Dice).props.state).toBe('rolling');
});

test('a new roll card starts from its own help, not the one picked on the card before', async () => {
  (getGame as jest.Mock).mockResolvedValue({ ...base, card: door });
  const next: GameView = { ...base, revision: 1, card: { ...door, id: 'c2' } };
  (sendCommand as jest.Mock).mockResolvedValue({ kind: 'card', turn: null, steps: [], reason: null, view: next } as CommandResult);
  await flush(async () => { tree = renderer.create(<Screen />); });
  await flush(async () => { (radio().props.onPress as () => void)(); });
  expect(radio().props.accessibilityState).toMatchObject({ checked: true });
  await flush(async () => { (pressable(ko.close).props.onPress as () => void)(); });
  expect(game.view?.card?.id).toBe('c2');
  expect(radio().props.accessibilityState).toMatchObject({ checked: false });
});

test('a server error on a roll shows its notice on the card, which stays open, and not under it', async () => {
  (getGame as jest.Mock).mockResolvedValue({ ...base, card: door });
  (sendCommand as jest.Mock).mockRejectedValueOnce(new ApiError(500, null, null));
  await flush(async () => { tree = renderer.create(<Screen />); });
  await flush(async () => { (pressable(ko.hold).props.onPress as () => void)(); });
  expect(game.phase).toBe('card');
  expect(tree!.root.findByType(RollCard).findAllByType(Text).map((t: Node) => t.props.children)).toContain(ko.serverError);
  expect(screenText().split(ko.serverError)).toHaveLength(2);
});

test('a chapter recap arriving after the narration is typed is typed too before commands open, and logged with it', async () => {
  const chapter: StepRecord = { ...walk, changes: [{ kind: 'chapter', from: 1, to: 2 }] };
  const view: GameView = { ...base, revision: 1, chapter: { k: 2, title: 'C2', aim: 'B' }, last: { turn: 1, steps: [chapter], narrated: false } };
  (getGame as jest.Mock).mockResolvedValue(base);
  (sendCommand as jest.Mock).mockResolvedValue({ kind: 'turn', turn: 1, steps: [chapter], reason: null, view } as CommandResult);
  let recap = () => undefined as void;
  (stream as jest.Mock).mockImplementation(async (path: string, on: (e: NarrationEvent) => void) => {
    if (path.startsWith('/r/')) await new Promise<void>((done) => { recap = done; });
    on({ type: 'text', text: path.startsWith('/r/') ? '지난 일입니다.' : TEXT });
    on({ type: 'done', tags: [] });
  });
  const tick = 1000 / motion.typeRate;
  await flush(async () => { tree = renderer.create(<Screen />); });
  await say('둘러본다');
  await flush(async () => { game.skip(); });
  await flush(async () => { jest.advanceTimersByTime(tick * (TEXT.length + 2)); });
  expect(chat()).toContain(TEXT);
  expect(game.phase).toBe('narrating');
  await flush(async () => { recap(); });
  await flush(async () => { jest.advanceTimersByTime(tick * 4); });
  expect(game.phase).toBe('narrating');
  expect(input().props.editable).toBe(false);
  await flush(async () => { jest.advanceTimersByTime(tick * 10); });
  expect(chat()).toContain('지난 일입니다.');
  expect(game.phase).toBe('idle');
  const saved = (storeLog as jest.Mock).mock.calls.at(-1)[1] as { id: string; text?: string }[];
  expect(saved.find((e) => e.id === 'story:1')?.text).toBe(`${TEXT}\n\n지난 일입니다.`);
});
