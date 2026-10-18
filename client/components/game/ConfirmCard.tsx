import { Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { ko } from '@/locale/ko';
import type { Card, Command } from '@/services/types';

export function ConfirmCard({ card, disabled, onSend }: { card: Card; disabled: boolean; onSend: (command: Command) => void }) {
  return (
    <View className="gap-2 border-t border-border-default px-6 py-3">
      <Text accessibilityRole="header" className="font-sans-semibold text-title text-danger-fg">{ko.confirmTitle}</Text>
      {card.steps.map((step, i) => <Text key={i} className="font-sans text-body text-fg-default">{step}</Text>)}
      <Text className="font-mono text-caption text-gold-fg">{ko.odds(...card.odds)}</Text>
      {card.costs.map((cost) => <Text key={cost} className="font-sans text-caption text-fg-muted">{cost}</Text>)}
      <View className="flex-row gap-3 pt-1">
        <View className="flex-1"><Button label={ko.cancel} disabled={disabled} onPress={() => onSend({ confirm: card.id, accept: false })} /></View>
        <View className="flex-1"><Button label={ko.accept} primary disabled={disabled} onPress={() => onSend({ confirm: card.id, accept: true })} /></View>
      </View>
    </View>
  );
}
