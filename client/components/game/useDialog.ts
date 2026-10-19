import { type RefObject, useEffect, useRef } from 'react';
import { Platform, type View } from 'react-native';

const FOCUSABLE = 'button:not([disabled]), [role="button"]:not([aria-disabled="true"]), [role="menuitem"], [role="radio"]:not([aria-disabled="true"]), input, textarea, [tabindex="0"]';

const open: object[] = [];

export function useDialog(onClose?: () => void): RefObject<View | null> {
  const ref = useRef<View | null>(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return undefined;
    const root = ref.current as unknown as HTMLElement | null;
    if (!root) return undefined;
    const opener = document.activeElement as HTMLElement | null;
    const me = {};
    open.push(me);
    const items = () => Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
    items()[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (open[open.length - 1] !== me) return;     // a menu over a card takes the keys first
      if (e.key === 'Escape' && close.current) {
        e.preventDefault();
        close.current();
      } else if (e.key === 'Tab') {
        const list = items();
        if (!list.length) return;
        const at = list.indexOf(document.activeElement as HTMLElement);
        const next = e.shiftKey ? (at <= 0 ? list.length - 1 : at - 1) : (at + 1) % list.length;
        e.preventDefault();
        list[next].focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      open.splice(open.indexOf(me), 1);
      if (opener && document.contains(opener)) opener.focus();
    };
  }, []);

  return ref;
}
