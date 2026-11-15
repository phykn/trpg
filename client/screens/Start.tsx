import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { Button, pressed } from '@/components/ui/Button';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

function Pick({ label, stats, chosen, other, onPick }: {
  label: string; stats: { key: string; name: string }[]; chosen: string | null; other: string | null;
  onPick: (key: string) => void;
}) {
  return (
    <View className="flex-row items-center gap-2">
      <Text className="w-8 font-mono-medium text-body text-gold-fg">{label}</Text>
      {stats.map((s) => {
        const on = chosen === s.key;
        return (
          <Pressable key={s.key} accessibilityRole="button" accessibilityLabel={`${label} ${s.name}`}
            accessibilityState={{ selected: on, disabled: other === s.key }} disabled={other === s.key}
            onPress={() => onPick(s.key)} style={pressed}
            className={`h-10 min-w-0 flex-1 items-center justify-center rounded-full border ${on ? 'border-gold-fg bg-gold-fg' : 'border-border-strong'} ${other === s.key ? 'opacity-40' : ''}`}>
            <Text className={`font-sans-semibold text-panel ${on ? 'text-fg-on-emphasis' : 'text-fg-default'}`}>{s.name}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Start({ view, locked, onStart }: { view: GameView; locked: boolean; onStart: (act: string) => void }) {
  const [plus2, setPlus2] = useState<string | null>(null);
  const [plus1, setPlus1] = useState<string | null>(null);
  const start = view.start!;
  const act = start.acts.find((a) => a.plus2 === plus2 && a.plus1 === plus1);
  return (
    <View className="min-h-0 flex-1 gap-4 px-4 py-6">
      <Text accessibilityRole="header" className="font-serif text-hero text-fg-default">{view.story.title}</Text>
      <ScrollView className="min-h-0 flex-1">
        <Text className="font-serif-body text-body text-fg-default">{start.intro}</Text>
      </ScrollView>
      <View className="gap-3">
        <Pick label={ko.plus2} stats={start.stats} chosen={plus2} other={plus1} onPick={setPlus2} />
        <Pick label={ko.plus1} stats={start.stats} chosen={plus1} other={plus2} onPick={setPlus1} />
        <Button label={ko.begin} disabled={!act || locked} onPress={() => act && onStart(act.id)} />
      </View>
    </View>
  );
}
