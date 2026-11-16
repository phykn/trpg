/**
 * @jest-environment jsdom
 */
import { act } from 'react';
// @ts-expect-error react-dom is available in Jest but has no local types.
import { createRoot } from 'react-dom/client';

import { useKeyboard } from '../useKeyboard';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// A stand-in visual viewport: an iPhone keyboard shrinks it and may scroll it down.
const viewport = Object.assign(new EventTarget(), { height: 800, offsetTop: 0 });
Object.defineProperty(window, 'visualViewport', { value: viewport, configurable: true });

let seen = { top: -1, height: -1 };
function Probe() {
  seen = useKeyboard();
  return null;
}

test('the frame follows the visible part of the page as the keyboard comes and goes', () => {
  const root = createRoot(document.body.appendChild(document.createElement('div')));
  act(() => { root.render(<Probe />); });
  expect(seen).toEqual({ top: 0, height: 800 });
  act(() => {
    Object.assign(viewport, { height: 460, offsetTop: 120 });
    viewport.dispatchEvent(new Event('scroll'));
  });
  expect(seen).toEqual({ top: 120, height: 460 });
  act(() => {
    Object.assign(viewport, { height: 800, offsetTop: 0 });
    viewport.dispatchEvent(new Event('resize'));
  });
  expect(seen).toEqual({ top: 0, height: 800 });
  act(() => { root.unmount(); });
});
