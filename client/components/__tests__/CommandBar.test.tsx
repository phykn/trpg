// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';
import { TextInput } from 'react-native';

import { CommandBar } from '@/components/game/CommandBar';
import { ko } from '@/locale/ko';

type Props = Parameters<typeof CommandBar>[0];
type Node = { props: Record<string, unknown> };

async function render(patch: Partial<Props>) {
  const props: Props = {
    mode: 'open', sent: null, notice: null, text: '', onText: jest.fn(), onSend: jest.fn(), onResend: jest.fn(), ...patch,
  };
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<CommandBar {...props} />); });
  const press = (label: string) => tree!.root.findAll((n: Node) => n.props.accessibilityLabel === label && typeof n.props.onPress === 'function');
  return { tree: tree!, props, press, inputs: () => tree!.root.findAllByType(TextInput) };
}

test('an open bar sends the trimmed sentence and clears it', async () => {
  const { props, inputs } = await render({ text: '  문을 연다 ' });
  await flush(async () => { inputs()[0].props.onSubmitEditing(); });
  expect(props.onSend).toHaveBeenCalledWith('문을 연다');
  expect(props.onText).toHaveBeenCalledWith('');
});

test('a locked bar takes no sentence', async () => {
  const { props, inputs } = await render({ mode: 'locked', text: '문을 연다' });
  expect(inputs()[0].props.editable).toBe(false);
  await flush(async () => { inputs()[0].props.onSubmitEditing(); });
  expect(props.onSend).not.toHaveBeenCalled();
});

test('a sending bar shows the sent sentence', async () => {
  const { inputs } = await render({ mode: 'sending', sent: '문을 연다', text: '' });
  expect(inputs()[0].props.value).toBe('문을 연다');
  expect(inputs()[0].props.editable).toBe(false);
});

test('a stuck bar offers only the resend, which resends', async () => {
  const { tree, props, press, inputs } = await render({ mode: 'stuck', text: '다른 문장' });
  expect(inputs()).toHaveLength(0);
  expect(JSON.stringify(tree.toJSON())).toContain(ko.stuck);
  await flush(async () => { press(ko.resend)[0].props.onPress(); });
  expect(props.onResend).toHaveBeenCalledTimes(1);
});

test('a notice is shown verbatim above the bar', async () => {
  const { tree } = await render({ notice: '문이 잠겨 있습니다.' });
  expect(JSON.stringify(tree.toJSON())).toContain('문이 잠겨 있습니다.');
});
