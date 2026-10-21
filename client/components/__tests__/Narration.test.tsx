// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { Chat } from '@/components/game/Narration';
import { motion } from '@/design/tokens';
import { ko } from '@/locale/ko';

type Props = Parameters<typeof Chat>[0];
type Node = { props: Record<string, unknown> };
const TEXT = '바람이 거셉니다.';
const tick = 1000 / motion.typeRate;

async function render(patch: Partial<Props>) {
  const props: Props = {
    entries: [], live: true, roll: null, waiting: true, hold: false, failed: false, onTyped: jest.fn(), onRetry: jest.fn(),
    narration: { text: TEXT, recap: null, error: null }, ...patch,
  };
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<Chat {...props} />); });
  return { tree: tree!, props, text: () => JSON.stringify(tree!.toJSON()) };
}

beforeEach(() => { jest.useFakeTimers(); });
afterEach(() => { jest.useRealTimers(); });

test('narration types in turn and counts as typed only once every character is shown', async () => {
  const { props, text } = await render({});
  await flush(async () => { jest.advanceTimersByTime(tick * 3); });
  expect(text()).toContain(TEXT.slice(0, 3));
  expect(text()).not.toContain(TEXT);
  expect(props.onTyped).not.toHaveBeenCalled();
  await flush(async () => { jest.advanceTimersByTime(tick * TEXT.length); });
  expect(text()).toContain(TEXT);
  expect(props.onTyped).toHaveBeenCalledTimes(1);
});

test('a tap shows the whole narration at once', async () => {
  const { tree, props } = await render({});
  const line = tree.root.findAll((n: Node) => n.props.accessibilityHint === ko.skip && typeof n.props.onPress === 'function')[0];
  await flush(async () => { (line.props.onPress as () => void)(); });
  expect(props.onTyped).toHaveBeenCalledTimes(1);
});

test('narration waits behind the dots while the reveal plays', async () => {
  const { props, text } = await render({ hold: true });
  await flush(async () => { jest.advanceTimersByTime(tick * (TEXT.length + 5)); });
  expect(text()).not.toContain(TEXT.slice(0, 2));
  expect(text()).toContain(ko.typing);
  expect(props.onTyped).not.toHaveBeenCalled();
});

test('a failed narration shows the server message under the fixed copy, with a retry', async () => {
  const { tree, props, text } = await render({ failed: true, narration: { text: null, recap: null, error: '모델이 응답하지 않습니다.' } });
  expect(text()).toContain(ko.narrationFailed);
  expect(text()).toContain('모델이 응답하지 않습니다.');
  const retry = tree.root.findAll((n: Node) => n.props.accessibilityLabel === ko.retryNarration && typeof n.props.onPress === 'function')[0];
  await flush(async () => { (retry.props.onPress as () => void)(); });
  expect(props.onRetry).toHaveBeenCalled();
});

// The chat stays mounted across turns, so nothing typed for the last turn may count toward the next: a carried-over
// count would open commands before a shorter narration is typed out, or never for the same narration twice.
async function nextTurn(first: string, second: string) {
  const onTyped = jest.fn();
  const props = (patch: Partial<Props>): Props => ({
    entries: [], live: true, roll: null, waiting: true, hold: false, failed: false, onTyped, onRetry: jest.fn(),
    narration: { text: first, recap: null, error: null }, ...patch,
  });
  const told = (text: string | null) => ({ text, recap: null, error: null });
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<Chat {...props({})} />); });
  await flush(async () => { jest.advanceTimersByTime(tick * (first.length + 2)); });
  expect(onTyped).toHaveBeenCalledTimes(1);
  // Logged, so no longer live; then the next turn reveals, and its text arrives while the reveal holds it.
  await flush(async () => { tree!.update(<Chat {...props({ live: false })} />); });
  await flush(async () => { tree!.update(<Chat {...props({ hold: true, narration: told(null) })} />); });
  await flush(async () => { tree!.update(<Chat {...props({ hold: true, narration: told(second) })} />); });
  await flush(async () => { tree!.update(<Chat {...props({ narration: told(second) })} />); });
  return onTyped;
}

test('a shorter narration after a longer one is typed out before it counts as typed', async () => {
  const onTyped = await nextTurn(TEXT, '조용합니다.');
  expect(onTyped).toHaveBeenCalledTimes(1);
  await flush(async () => { jest.advanceTimersByTime(tick * 10); });
  expect(onTyped).toHaveBeenCalledTimes(2);
});

test('the same narration twice in a row still counts as typed', async () => {
  const onTyped = await nextTurn(TEXT, TEXT);
  await flush(async () => { jest.advanceTimersByTime(tick * (TEXT.length + 2)); });
  expect(onTyped).toHaveBeenCalledTimes(2);
});

test('a recap arriving after the narration is typed carries on from there and counts as typed again', async () => {
  const { tree, props, text } = await render({});
  await flush(async () => { jest.advanceTimersByTime(tick * (TEXT.length + 2)); });
  expect(props.onTyped).toHaveBeenCalledTimes(1);
  const recap = { text: TEXT, recap: '지난 일입니다.', error: null };
  await flush(async () => { tree.update(<Chat {...props} narration={recap} />); });
  await flush(async () => { jest.advanceTimersByTime(tick * 3); });
  expect(text()).toContain(JSON.stringify(`${TEXT}\n\n지`).slice(1, -1));
  expect(text()).not.toContain('지난 일입니다.');
  expect(props.onTyped).toHaveBeenCalledTimes(1);
  await flush(async () => { jest.advanceTimersByTime(tick * 10); });
  expect(text()).toContain('지난 일입니다.');
  expect(props.onTyped).toHaveBeenCalledTimes(2);
});
