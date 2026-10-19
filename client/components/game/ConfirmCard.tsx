import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { Card } from '@/services/types';
import { Choice, Shell } from './CardShell';

/** ui.md 5.2: a high step that does not roll, with its effects. */
export function ConfirmCard({ card, onPick, onCancel }: { card: Card; onPick: (id: string) => void; onCancel: () => void }) {
  const o = card.options[0];
  return (
    <Shell title={o.label} onClose={onCancel}>
      <Text className="font-sans-semibold text-panel text-danger-fg">{ko.highRisk}</Text>
      {(o.effects ?? []).map((e) => <Text key={e} className="font-sans text-body text-fg-default">· {e}</Text>)}
      <View className="mt-auto gap-2">
        <Choice primary label={ko.choose} onPress={() => onPick(o.id)} />
        <Choice label={ko.cancel} onPress={onCancel} />
      </View>
    </Shell>
  );
}
