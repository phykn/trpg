/**
 * @jest-environment jsdom
 */
// The hook acts only on web, where the dialog's ref is a DOM node, so this runs in a DOM with Platform.OS 'web'.
import { act } from 'react';
// @ts-expect-error react-dom is available in Jest but has no local types.
import { createRoot } from 'react-dom/client';
import { Platform } from 'react-native';

import { useDialog } from '../useDialog';

jest.replaceProperty(Platform, 'OS', 'web');
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function Dialog({ name, onClose }: { name: string; onClose?: () => void }) {
  const ref = useDialog(onClose) as unknown as React.RefObject<HTMLDivElement>;
  return (
    <div ref={ref} role="dialog" aria-label={name}>
      <button type="button">{`${name} first`}</button>
      <button type="button">{`${name} last`}</button>
    </div>
  );
}

let root: { render: (node: React.ReactNode) => void; unmount: () => void };
const render = (node: React.ReactNode) => act(() => { root.render(node); });
const press = (key: string, shiftKey = false) => act(() => {
  document.dispatchEvent(new KeyboardEvent('keydown', { key, shiftKey, bubbles: true, cancelable: true }));
});
const focused = () => document.activeElement?.getAttribute('aria-label') ?? document.activeElement?.textContent;

beforeEach(() => {
  const host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => { root.unmount(); });
  document.body.innerHTML = '';
});

test('the dialog takes focus, Escape closes it, and focus returns to its opener', async () => {
  const opener = document.createElement('button');
  document.body.appendChild(opener);
  opener.focus();
  const onClose = jest.fn();
  render(<Dialog name="card" onClose={onClose} />);
  expect(focused()).toBe('card');
  press('Escape');
  expect(onClose).toHaveBeenCalledTimes(1);
  render(null);
  // focus-trap hands focus back on the next tick.
  await act(() => new Promise((resolve) => { setTimeout(resolve, 0); }));
  expect(document.activeElement).toBe(opener);
});

test('Tab and Shift+Tab stay inside the dialog', () => {
  render(<Dialog name="card" onClose={jest.fn()} />);
  press('Tab');
  expect(focused()).toBe('card first');
  press('Tab');
  press('Tab');
  expect(focused()).toBe('card first');
  press('Tab', true);
  expect(focused()).toBe('card last');
});

test('only the newest dialog answers Escape, and one that cannot close ignores it', () => {
  const card = jest.fn();
  const menu = jest.fn();
  render(<><Dialog name="card" onClose={card} /><Dialog name="menu" onClose={menu} /></>);
  press('Escape');
  expect([menu.mock.calls.length, card.mock.calls.length]).toEqual([1, 0]);
  render(<Dialog name="card" onClose={card} />);
  press('Escape');
  expect(card).toHaveBeenCalledTimes(1);
  render(<Dialog name="locked" />);
  expect(() => press('Escape')).not.toThrow();
});
