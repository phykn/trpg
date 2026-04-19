import React from 'react';
import { View, Keyboard } from 'react-native';
import { useGame } from '@/hooks/use-game';
import { buildPanelSlots } from '@/services';
import { ContextCard } from './header';
import { Log } from './log';
import { HeroPill } from './hero';
import { Composer } from './composer';

export function Shell() {
  const { hero, subject, quest, place, log, rolling, rollEnabled, streaming, onSend, onRoll, onStop } = useGame();
  const slots = buildPanelSlots({ subject, quest, place });

  const [typing, setTyping] = React.useState(false);
  const [activeId, setActiveId] = React.useState<string | null>('person');
  const [heroOpen, setHeroOpen] = React.useState(false);

  React.useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', () => setTyping(true));
    const hide = Keyboard.addListener('keyboardDidHide', () => setTyping(false));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  React.useEffect(() => {
    if (typing) {
      setActiveId(null);
      setHeroOpen(false);
    }
  }, [typing]);

  return (
    <View className="flex-1 bg-canvas-default py-2.5 gap-2.5">
      <ContextCard
        slots={slots}
        activeId={activeId}
        onSelect={(id) => setActiveId((prev) => (prev === id ? null : id))}
        onCollapse={() => setActiveId(null)}
      />

      <Log log={log} rolling={rolling} />

      <HeroPill hero={hero} expanded={heroOpen} onToggle={() => setHeroOpen((v) => !v)} />

      <Composer
        onSend={onSend}
        onRoll={onRoll}
        onStop={onStop}
        rolling={rolling}
        focused={typing}
        rollEnabled={rollEnabled}
        streaming={streaming}
      />
    </View>
  );
}
