import { Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Card } from '@/services/types';

// A choice that cannot be taken back: its effects in plain lines, one button to commit.
export function ConfirmCard({ card, onPick, onCancel }: { card: Card; onPick: (id: string) => void; onCancel: () => void }) {
  const o = card.options[0];
  return (
    <Sheet title={o.label} icon="alert" tone={colors.danger.fg} onClose={onCancel}>
      {(o.effects ?? []).length ? (
        <View accessibilityLabel={ko.highRisk} className="gap-1.5 rounded-xl bg-canvas-subtle px-4 py-3">
          {(o.effects ?? []).map((e) => (
            <View key={e} className="flex-row gap-2">
              <View className="mt-[9px] h-1 w-1 rounded-full bg-danger-fg" />
              <Text className="min-w-0 flex-1 font-sans text-panel text-fg-default">{e}</Text>
            </View>
          ))}
        </View>
      ) : null}
      <Button icon="check" label={ko.choose} onPress={() => onPick(o.id)} />
    </Sheet>
  );
}
