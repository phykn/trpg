import { createFocusTrap } from 'focus-trap';
import { type RefObject, useEffect, useRef } from 'react';
import { Platform, type View } from 'react-native';

// On web: focus moves into the dialog, Tab stays inside it, Escape closes it, and focus returns to the opener.
// focus-trap keeps a stack of traps, so only the newest dialog answers the keys.
export function useDialog(onClose?: () => void): RefObject<View | null> {
  const ref = useRef<View | null>(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    const root = ref.current as unknown as HTMLElement | null;
    if (Platform.OS !== 'web' || !root) return undefined;
    // The panel takes focus, not its first control, so the Enter that sent a command does not press that control.
    root.tabIndex = -1;
    root.style.outline = 'none';
    const trap = createFocusTrap(root, {
      initialFocus: root,
      delayInitialFocus: false,
      fallbackFocus: root,
      preventScroll: true,
      // The trap stays until the dialog leaves; Escape only asks it to close.
      escapeDeactivates: () => {
        close.current?.();
        return false;
      },
      allowOutsideClick: true,
      returnFocusOnDeactivate: true,
      // Layout checks need a real browser; react-native-web never hides a control it renders.
      tabbableOptions: { displayCheck: 'none' },
    });
    trap.activate();
    return () => {
      trap.deactivate();
    };
  }, []);

  return ref;
}
