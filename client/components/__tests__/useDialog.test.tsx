/**
 * @jest-environment jsdom
 */
// The hook acts only on web, where the dialog's ref is a DOM node, so this runs in a DOM with Platform.OS 'web'.
import { act } from 'react';
// @ts-expect-error react-dom is available in Jest but has no local types.
import { createRoot } from 'react-dom/client';
import { Platform } from 'react-native';

import { useDialog } from '@/components/ui/useDialog';

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

let host: HTMLDivElement;
let root: { render: (node: React.ReactNode) => void; unmount: () => void };
function render(node: React.ReactNode) { act(() => { root.render(node); }); }
const press = (key: string, shiftKey = false) => act(() => {
  document.dispatchEvent(new KeyboardEvent('keydown', { key, shiftKey, bubbles: true, cancelable: true }));
});
const button = (text: string) => [...document.querySelectorAll('button')].find((b) => b.textContent === text) as HTMLButtonElement;

beforeEach(() => {
  host = document.createElement('div');
  document.body.appendChild(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => { root.unmount(); });
  document.body.innerHTML = '';
});

test('Escape closes the dialog, and focus returns to what opened it', () => {
  const opener = document.createElement('button');
  document.body.appendChild(opener);
  opener.focus();
  const onClose = jest.fn();
  render(<Dialog name="card" onClose={onClose} />);
  expect(document.activeElement?.getAttribute('aria-label')).toBe('card');
  press('Escape');
  expect(onClose).toHaveBeenCalledTimes(1);
  render(null);
  expect(document.activeElement).toBe(opener);
});

test('Tab cycles inside the dialog', () => {
  render(<Dialog name="card" onClose={jest.fn()} />);
  press('Tab');
  expect(document.activeElement).toBe(button('card first'));
  press('Tab');
  press('Tab');
  expect(document.activeElement).toBe(button('card first'));
  press('Tab', true);
  expect(document.activeElement).toBe(button('card last'));
});

test('a menu over a card takes Escape first; the card gets it once the menu is gone', () => {
  const card = jest.fn();
  const menu = jest.fn();
  render(<><Dialog name="card" onClose={card} /><Dialog name="menu" onClose={menu} /></>);
  press('Escape');
  expect(menu).toHaveBeenCalledTimes(1);
  expect(card).not.toHaveBeenCalled();
  render(<Dialog name="card" onClose={card} />);
  press('Escape');
  expect(card).toHaveBeenCalledTimes(1);
});

test('a locked dialog ignores Escape', () => {
  render(<Dialog name="card" />);
  expect(() => press('Escape')).not.toThrow();
});
