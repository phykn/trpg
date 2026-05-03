import React from 'react';
import { useAudioPlayer } from 'expo-audio';
import type { AudioStatus } from 'expo-audio';

const BGM_LIST = [
  require('../../assets/audio/bgm/bgm-01.mp3'),
];

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function useBgm() {
  const orderRef = React.useRef<number[]>([]);
  const idxRef = React.useRef(0);

  if (orderRef.current.length === 0) {
    orderRef.current = shuffle(BGM_LIST.map((_, i) => i));
    idxRef.current = 0;
  }

  const [currentSource, setCurrentSource] = React.useState(
    () => BGM_LIST[orderRef.current[idxRef.current]],
  );
  const player = useAudioPlayer(currentSource);
  const [bgmOn, setBgmOn] = React.useState(false);

  // Single-track shortcut: keep loop on. Multi-track: rely on didJustFinish.
  React.useEffect(() => {
    player.loop = BGM_LIST.length === 1;
  }, [player]);

  const advance = React.useCallback(() => {
    if (BGM_LIST.length <= 1) return;
    idxRef.current += 1;
    if (idxRef.current >= orderRef.current.length) {
      orderRef.current = shuffle(BGM_LIST.map((_, i) => i));
      idxRef.current = 0;
    }
    setCurrentSource(BGM_LIST[orderRef.current[idxRef.current]]);
  }, []);

  React.useEffect(() => {
    const sub = player.addListener('playbackStatusUpdate', (status: AudioStatus) => {
      if (status.didJustFinish) advance();
    });
    return () => sub.remove();
  }, [player, advance]);

  // After advance swaps source, autoplay if user had BGM on.
  const bgmOnRef = React.useRef(bgmOn);
  React.useEffect(() => {
    bgmOnRef.current = bgmOn;
  }, [bgmOn]);
  React.useEffect(() => {
    if (bgmOnRef.current) player.play();
  }, [player]);

  const toggle = React.useCallback(() => {
    setBgmOn((on) => {
      if (on) player.pause();
      else player.play();
      return !on;
    });
  }, [player]);

  return { bgmOn, toggle };
}
