import React from 'react';
import { View, Keyboard } from 'react-native';
import { Theme } from '@/constants/theme';
import { useGame } from '@/hooks/use-game';
import { usePanels } from '@/hooks/use-panels';
import { ContextCard } from './header';
import { Log } from './log';
import { HeroPill } from './hero';
import { Composer } from './composer';

export function Shell() {
  const { hero, subject, quest, place, log, rolling, rollEnabled, onSend, onRoll } = useGame();
  const slots = usePanels(subject, quest, place);

  const [typing, setTyping] = React.useState(false);
  const [activeId, setActiveId] = React.useState<string | null>('person');
  const [heroOpen, setHeroOpen] = React.useState(false);

  const prevTyping = React.useRef(typing);
  React.useEffect(() => {
    if (typing && !prevTyping.current) setActiveId(null);
    prevTyping.current = typing;
  }, [typing]);

  return (
    <View style={{
      flex: 1, backgroundColor: Theme.bg,
      paddingVertical: Theme.space.md - 2,
      gap: Theme.space.md - 2,
    }}>
      <ContextCard
        slots={slots}
        activeId={activeId}
        onSelect={(id) => setActiveId(prev => (prev === id ? null : id))}
      />

      <Log log={log} rolling={rolling} />

      <HeroPill hero={hero} expanded={heroOpen} onToggle={() => setHeroOpen(v => !v)} />

      <Composer
        onSend={onSend}
        onRoll={onRoll}
        rolling={rolling}
        focused={typing}
        onFocus={() => setTyping(true)}
        onBlur={() => { setTyping(false); Keyboard.dismiss(); }}
        rollEnabled={rollEnabled}
      />
    </View>
  );
}
