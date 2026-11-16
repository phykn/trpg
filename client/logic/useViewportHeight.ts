import { useEffect, useState } from 'react';
import { useWindowDimensions } from 'react-native';

// The visual viewport shrinks while a phone's keyboard is up, so the frame and its input stay above the keyboard.
export function useViewportHeight() {
  const { height } = useWindowDimensions();
  const [visible, setVisible] = useState(height);
  useEffect(() => {
    const target = window.visualViewport ?? window;
    const update = () => setVisible(window.visualViewport?.height ?? window.innerHeight);
    update();
    target.addEventListener('resize', update);
    return () => target.removeEventListener('resize', update);
  }, []);
  return visible;
}
