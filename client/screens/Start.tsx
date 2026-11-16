import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { Button, pressed } from '@/components/ui/Button';
import { control, off, surface, text, tone } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

type Stats = NonNullable<GameView['start']>['stats'];

// One row per bonus; the stat the other row took cannot be taken twice.
function StatRow({ label, stats, chosen, taken, onPick }: {
  label: string; stats: Stats; chosen: string | null; taken: string | null; onPick: (key: string) => void;
}) {
  return (
    <View className="flex-row items-center gap-2">
      <Text className="w-8 font-mono-medium text-body text-gold-fg">{label}</Text>
      {stats.map(({ key, name }) => (
        <Pressable key={key} accessibilityRole="button" accessibilityLabel={`${label} ${name}`}
          accessibilityState={{ selected: chosen === key, disabled: taken === key }} disabled={taken === key}
          onPress={() => onPick(key)} style={pressed}
          className={`${control.tab} ${chosen === key ? tone.picked : tone.idle} ${taken === key ? off : ''}`}>
          <Text className={chosen === key ? text.labelOn : text.label}>{name}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export function Start({ view, locked, onStart }: { view: GameView; locked: boolean; onStart: (act: string) => void }) {
  const [plus2, setPlus2] = useState<string | null>(null);
  const [plus1, setPlus1] = useState<string | null>(null);
  const start = view.start!;
  const act = start.acts.find((a) => a.plus2 === plus2 && a.plus1 === plus1);
  return (
    <View className={surface.screen}>
      <Text accessibilityRole="header" className={text.hero}>{view.story.title}</Text>
      <ScrollView className="min-h-0 flex-1">
        <Text className={text.scene}>{start.intro}</Text>
      </ScrollView>
      <View className="gap-3">
        <StatRow label={ko.plus2} stats={start.stats} chosen={plus2} taken={plus1} onPick={setPlus2} />
        <StatRow label={ko.plus1} stats={start.stats} chosen={plus1} taken={plus2} onPick={setPlus1} />
        <Button label={ko.begin} disabled={!act || locked} onPress={() => act && onStart(act.id)} />
      </View>
    </View>
  );
}
