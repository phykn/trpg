import { Choice, Sheet } from '@/components/ui/Sheet';
import type { Card } from '@/services/types';

// The sentence is already in the chat above, so the card asks and lists the answers, nothing more.
export function ClarifyCard({ card, onPick, onCancel }: { card: Card; onPick: (id: string) => void; onCancel: () => void }) {
  return (
    <Sheet title={card.question} onClose={onCancel}>
      {card.options.map((o) => <Choice key={o.id} label={o.label} onPress={() => onPick(o.id)} />)}
    </Sheet>
  );
}
