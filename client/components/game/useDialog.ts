import { type RefObject, useEffect, useRef } from 'react';
import { Platform, type View } from 'react-native';

const FOCUSABLE = 'button:not([disabled]), [role="button"]:not([aria-disabled="true"]), [role="radio"]:not([aria-disabled="true"]), input, textarea, [tabindex="0"]';

/** A card as a dialog on web: Escape closes it, Tab stays inside, and focus returns to the opener. */
export function useDialog(onClose?: () => void): RefObject<View | null> {
  const ref = useRef<View | null>(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return undefined;
    const root = ref.current as unknown as HTMLElement | null;
    if (!root) return undefined;
    const opener = document.activeElement as HTMLElement | null;
    const items = () => Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
    items()[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
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
      if (opener && document.contains(opener)) opener.focus();
    };
  }, []);

  return ref;
}
