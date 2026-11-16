import { useEffect, useState } from 'react';
import { useWindowDimensions } from 'react-native';

// The part of the page the on-screen keyboard leaves visible (the visual viewport). On iPhone the keyboard only
// shrinks the visual viewport and may scroll it (offsetTop); on Android the window itself shrinks. The frame takes
// exactly this box, so the input sits right on the keyboard and the top bar stays in view.
export function useKeyboard() {
  const window_ = useWindowDimensions();
  const [box, setBox] = useState({ top: 0, height: window_.height });
  useEffect(() => {
    const vv = window.visualViewport;
    const read = () => {
      const next = vv ? { top: Math.round(vv.offsetTop), height: Math.round(vv.height) } : { top: 0, height: window.innerHeight };
      setBox((was) => (was.top === next.top && was.height === next.height ? was : next));
    };
    read();
    window.addEventListener('resize', read);
    vv?.addEventListener('resize', read);
    vv?.addEventListener('scroll', read);
    return () => {
      window.removeEventListener('resize', read);
      vv?.removeEventListener('resize', read);
      vv?.removeEventListener('scroll', read);
    };
  }, []);
  return box;
}
