import { Text } from 'react-native';

import { ko } from '@/locale/ko';
import type { Card } from '@/services/types';
import { Choice, Shell } from './CardShell';

/** ui.md 5.2: at most three readings of the sentence, and cancel. */
export function ClarifyCard({ card, onPick, onCancel }: { card: Card; onPick: (id: string) => void; onCancel: () => void }) {
  return (
    <Shell title={card.question}>
      <Text className="font-sans text-body text-fg-muted">“{card.echo.text}”</Text>
      {card.options.map((o) => <Choice key={o.id} label={o.label} onPress={() => onPick(o.id)} />)}
      <Choice label={ko.cancel} onPress={onCancel} />
    </Shell>
  );
}
