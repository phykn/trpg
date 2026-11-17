import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Button, pressed } from '@/components/ui/Button';
import { Icon, type IconName } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, surface, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

const STAT_ICONS: Record<string, IconName> = { charm: 'charm', might: 'might', wit: 'wit', skill: 'skill' };

type Bonus = Record<string, number>;

// A stat raised to a bonus another holds takes it; the other drops back to 0, so nothing needs undoing.
function setBonus(bonus: Bonus, key: string, value: number): Bonus {
  const next = Object.fromEntries(Object.entries(bonus).map(([k, v]) => [k, value > 0 && v === value ? 0 : v]));
  return { ...next, [key]: value };
}

function Step({ label, down, off, onPress }: { label: string; down?: boolean; off: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: off }} disabled={off}
      onPress={onPress} style={pressed} className={control({ kind: 'step', tone: off ? 'plain' : 'quiet', off })}>
      <Icon name="step" size={icon.sm} color={colors.fg.default} fill flip={down} />
    </Pressable>
  );
}

function StatRow({ name, statKey, value, onSet }: { name: string; statKey: string; value: number; onSet: (v: number) => void }) {
  const on = value > 0;
  return (
    <View className={control({ kind: 'row', tone: value === 2 ? 'offer' : on ? 'focus' : 'quiet' }, 'pr-2', on && 'border-2')}>
      <Icon name={STAT_ICONS[statKey] ?? 'person'} size={icon.lg} color={on ? colors.gold.fg : colors.fg.muted} width={2} />
      <Text className={text({ kind: 'strong' }, 'min-w-0 flex-1')}>{name}</Text>
      <Step label={ko.lower(name)} down off={value === 0} onPress={() => onSet(value - 1)} />
      <Text accessibilityLabel={`${name} ${value}`} className={text({ kind: 'value' }, on ? 'text-gold-fg' : 'text-fg-subtle')}>
        {value ? `+${value}` : '0'}
      </Text>
      <Step label={ko.raise(name)} off={value === 2} onPress={() => onSet(value + 1)} />
    </View>
  );
}

export function Start({ view, locked, onStart }: { view: GameView; locked: boolean; onStart: (act: string) => void }) {
  const start = view.start!;
  const [bonus, setBonusState] = useState<Bonus>(() => Object.fromEntries(start.stats.map((s) => [s.key, 0])));
  const keyOf = (v: number) => Object.keys(bonus).find((k) => bonus[k] === v);
  const plus2 = keyOf(2);
  const plus1 = keyOf(1);
  const remaining = [plus2 ? 0 : 2, plus1 ? 0 : 1].filter(Boolean);
  const act = start.acts.find((a) => a.plus2 === plus2 && a.plus1 === plus1);
  return (
    <View className={surface({ kind: 'screen' })}>
      <Text accessibilityRole="header" className={text({ kind: 'hero' })}>{view.story.title}</Text>
      {/* The case is told by the first person in the game, not here (docs/game/07-screen.md 1). */}
      <View className="min-h-0 flex-1" />
      <View className="gap-2">
        <Text accessibilityLiveRegion="polite" className={text({ kind: 'sub' }, 'min-h-5')}>
          {remaining.length ? ko.remainingBonuses(remaining) : ''}
        </Text>
        {start.stats.map(({ key, name }) => (
          <StatRow key={key} name={name} statKey={key} value={bonus[key]} onSet={(v) => setBonusState(setBonus(bonus, key, v))} />
        ))}
      </View>
      <Button label={ko.begin} disabled={!act || locked} onPress={() => act && onStart(act.id)} />
    </View>
  );
}
