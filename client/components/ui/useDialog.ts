import { type RefObject, useEffect, useRef } from 'react';
import { Platform, type View } from 'react-native';

const FOCUSABLE = 'button:not([disabled]), [role="button"]:not([aria-disabled="true"]), [role="menuitem"], [role="radio"]:not([aria-disabled="true"]), input, textarea, [tabindex="0"]';

// Open dialogs, newest last: only the top one answers the keys.
const stack: object[] = [];

// On web: focus moves into the dialog, Tab stays inside it, Escape closes it, and focus returns to the opener.
export function useDialog(onClose?: () => void): RefObject<View | null> {
  const ref = useRef<View | null>(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    const root = ref.current as unknown as HTMLElement | null;
    if (Platform.OS !== 'web' || !root) return undefined;
    const opener = document.activeElement as HTMLElement | null;
    const me = {};
    stack.push(me);
    // The panel takes focus, not its first control, so the Enter that sent a command does not press that control.
    root.tabIndex = -1;
    root.style.outline = 'none';
    root.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== me) return;
      if (e.key === 'Escape' && close.current) {
        e.preventDefault();
        close.current();
      } else if (e.key === 'Tab') {
        const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
        if (!items.length) return;
        const at = items.indexOf(document.activeElement as HTMLElement);
        e.preventDefault();
        items[e.shiftKey ? (at <= 0 ? items.length - 1 : at - 1) : (at + 1) % items.length].focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      stack.splice(stack.indexOf(me), 1);
      if (opener && document.contains(opener)) opener.focus();
    };
  }, []);

  return ref;
}
