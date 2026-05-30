import React from 'react';
import { Keyboard, Platform, type KeyboardEvent } from 'react-native';

type NavigatorWithVirtualKeyboard = Navigator & {
  virtualKeyboard?: EventTarget & { boundingRect: DOMRectReadOnly };
};

function isEditableElementFocused() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  return tag === 'input' || tag === 'textarea' || el.getAttribute('contenteditable') === 'true';
}

export function useKeyboardOverlay() {
  const [typing, setTyping] = React.useState(false);
  const [keyboardOverlayHeight, setKeyboardOverlayHeight] = React.useState(0);

  React.useEffect(() => {
    if (Platform.OS === 'web') {
      const updateWebKeyboardOverlayHeight = () => {
        const webNavigator = navigator as NavigatorWithVirtualKeyboard;
        const keyboardHeight = webNavigator.virtualKeyboard?.boundingRect.height ?? 0;
        const visualViewportHeight = isEditableElementFocused() && window.visualViewport
          ? Math.max(0, window.innerHeight - window.visualViewport.height - window.visualViewport.offsetTop)
          : 0;
        const nextHeight = Math.max(keyboardHeight, visualViewportHeight);
        setTyping(nextHeight > 0);
        setKeyboardOverlayHeight(nextHeight);
      };
      const webNavigator = navigator as NavigatorWithVirtualKeyboard;
      webNavigator.virtualKeyboard?.addEventListener('geometrychange', updateWebKeyboardOverlayHeight);
      window.visualViewport?.addEventListener('resize', updateWebKeyboardOverlayHeight);
      window.visualViewport?.addEventListener('scroll', updateWebKeyboardOverlayHeight);
      updateWebKeyboardOverlayHeight();
      return () => {
        webNavigator.virtualKeyboard?.removeEventListener('geometrychange', updateWebKeyboardOverlayHeight);
        window.visualViewport?.removeEventListener('resize', updateWebKeyboardOverlayHeight);
        window.visualViewport?.removeEventListener('scroll', updateWebKeyboardOverlayHeight);
      };
    }

    const show = Keyboard.addListener('keyboardDidShow', (ev: KeyboardEvent) => {
      setTyping(true);
      setKeyboardOverlayHeight(ev.endCoordinates.height);
    });
    const hide = Keyboard.addListener('keyboardDidHide', () => {
      setTyping(false);
      setKeyboardOverlayHeight(0);
    });
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  return { typing, keyboardOverlayHeight };
}
