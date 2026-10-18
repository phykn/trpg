import { Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import type { Button as Choice } from '@/services/types';

export function Choices({ title, options, disabled, onPick, extra }: {
  title: string;
  options: Choice[];
  disabled: boolean;
  onPick: (id: string) => void;
  extra?: { label: string; onPress: () => void };
}) {
  return (
    <View className="gap-2 border-t border-border-default px-6 py-3">
      <Text accessibilityRole="header" className="font-sans-semibold text-body text-gold-fg">{title}</Text>
      {options.map((o) => <Button key={o.id} label={o.label} disabled={disabled} onPress={() => onPick(o.id)} />)}
      {extra ? <Button label={extra.label} onPress={extra.onPress} /> : null}
    </View>
  );
}
