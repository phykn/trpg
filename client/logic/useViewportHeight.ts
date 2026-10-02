import { useEffect, useState } from 'react';
import { useWindowDimensions } from 'react-native';

export function useViewportHeight() {
  const { height } = useWindowDimensions();
  const [visible, setVisible] = useState(height);
  useEffect(() => {
    const viewport = window.visualViewport;
    const update = () => setVisible(viewport?.height ?? window.innerHeight);
    update();
    viewport?.addEventListener('resize', update);
    window.addEventListener('resize', update);
    return () => {
      viewport?.removeEventListener('resize', update);
      window.removeEventListener('resize', update);
    };
  }, []);
  return visible;
}
