import { Pressable, ScrollView, Text } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { ko } from '@/locale/ko';
import type { Act } from '@/services/types';

// The bets a typed action could lead to, offered right after it; each label says all it does.
export function OffersRow({ offers, locked, onAct }: { offers: Act[]; locked: boolean; onAct: (act: string) => void }) {
  if (!offers.length) return null;
  return (
    <ScrollView horizontal accessibilityLabel={ko.offers} showsHorizontalScrollIndicator={false}
      className="grow-0" contentContainerClassName="gap-2 px-3 pt-2">
      {offers.map((a) => (
        <Pressable key={a.id} accessibilityRole="button" accessibilityLabel={a.label} accessibilityState={{ disabled: locked }}
          disabled={locked} onPress={() => onAct(a.id)} style={pressed}
          className={`h-9 flex-row items-center justify-center rounded-full border border-gold-fg bg-gold-muted px-4 ${locked ? 'opacity-60' : ''}`}>
          <Text className="font-sans-semibold text-panel text-fg-default">{a.label}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}
