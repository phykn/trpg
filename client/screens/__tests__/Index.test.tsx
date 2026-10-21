// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';
import { TextInput } from 'react-native';

import Index from '@/app/index';
import { motion } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { ApiError, createGame, getStories } from '@/services/api';
import type { GameView, Story } from '@/services/types';

jest.mock('@/logic/useViewportHeight', () => ({ useViewportHeight: () => 800 }));
jest.mock('expo-router/head', () => ({ __esModule: true, default: () => null }));
jest.mock('@/services/api', () => ({
  ApiError: class extends Error {
    status: number; view: unknown; reason: unknown;
    constructor(status: number, view: unknown, reason: unknown) { super('x'); this.status = status; this.view = view; this.reason = reason; }
  },
  getStories: jest.fn(), getGame: jest.fn(), sendCommand: jest.fn(), createGame: jest.fn(), stream: jest.fn(),
  narrationPath: () => '', recapPath: () => '',
}));
jest.mock('@/services/storage', () => ({
  loadGameId: jest.fn(() => null), storeGameId: jest.fn(() => true), clearGameId: jest.fn(),
  loadLog: jest.fn(() => []), storeLog: jest.fn(),
}));

// Nothing to place or pick, so the start button is ready at once.
const story: Story = { id: 's', title: 'S', premise: '등대가 꺼졌습니다.', approaches: [], pick: 0, approach_names: [], traits: [] };
const view: GameView = {
  revision: 0, story: { id: 's', title: 'S', premise: story.premise }, chapter: { k: 1, title: 'C', aim: 'A' },
  scene: { place: { id: 'dock', name: '선착장', senses: [] }, people: [], things: [], obstacles: [], exits: [], tags: [] },
  player: { name: 'N', approaches: [], traits: [], tags: [], things: [], wounds: 0, wound_boxes: 2, beats: 0, beats_max: 6, growth: 0 },
  clocks: [], journal: { beliefs: [], owes: [], relations: [], choices: [] },
  buttons: [], growth: [], card: null, last: null, recaps: [], ending: null,
};

type Node = { props: Record<string, unknown> };
let tree: ReturnType<typeof renderer.create> | undefined;
const text = () => JSON.stringify(tree!.toJSON());
const button = (label: string) => tree!.root.findAll((n: Node) => n.props.accessibilityLabel === label && typeof n.props.onPress === 'function')[0];
const press = async (label: string) => { await flush(async () => { (button(label).props.onPress as () => void)(); }); };

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  (getStories as jest.Mock).mockResolvedValue([story]);
});
afterEach(async () => { await flush(async () => { tree?.unmount(); }); jest.useRealTimers(); });

async function create() {
  await flush(async () => { tree = renderer.create(<Index />); });
  await press(ko.begin);
  await press(ko.create);
}

test('a lost answer to creating the first game offers the resend, which sends the identical request', async () => {
  (createGame as jest.Mock).mockRejectedValueOnce(new TypeError('network')).mockResolvedValueOnce({ game_id: 'g_1', view });
  await create();
  expect(text()).not.toContain(ko.loading);
  expect(text()).toContain(ko.stuck);
  expect(button(ko.create)).toBeUndefined();
  await press(ko.resend);
  const [first, second] = (createGame as jest.Mock).mock.calls;
  expect(second).toEqual(first);
  expect(tree!.root.findAllByType(TextInput)[0].props.editable).toBe(true);
});

test('no answer within 30 seconds while creating offers the resend too', async () => {
  (createGame as jest.Mock).mockReturnValueOnce(new Promise(() => undefined));
  await create();
  expect(text()).not.toContain(ko.stuck);
  await flush(async () => { jest.advanceTimersByTime(motion.stuck); });
  expect(text()).toContain(ko.stuck);
  expect(button(ko.resend)).toBeDefined();
});

test('a server error while creating returns to the form with a notice and the start button', async () => {
  (createGame as jest.Mock).mockRejectedValueOnce(new ApiError(500, null, null));
  await create();
  expect(text()).toContain(ko.serverError);
  expect(button(ko.create)).toBeDefined();
  expect(text()).not.toContain(ko.stuck);
});
