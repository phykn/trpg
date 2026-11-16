import { Pressable, ScrollView, Text } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { Act } from '@/services/types';

export function OffersRow({ offers, locked, onAct }: { offers: Act[]; locked: boolean; onAct: (act: string) => void }) {
  if (!offers.length) return null;
  return (
    <ScrollView horizontal accessibilityLabel={ko.offers} showsHorizontalScrollIndicator={false}
      className="grow-0" contentContainerClassName="gap-2 px-3 pt-2">
      {offers.map((a) => (
        <Pressable key={a.id} accessibilityRole="button" accessibilityLabel={a.label} accessibilityState={{ disabled: locked }}
          disabled={locked} onPress={() => onAct(a.id)} style={pressed}
          className={control({ kind: 'pill', tone: 'offer', off: locked })}>
          <Text className={text({ kind: 'label' })}>{a.label}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}
