import { Choice, Sheet } from '@/components/ui/Sheet';
import { ko } from '@/locale/ko';
import type { Card, CardOption } from '@/services/types';

// A way that rolls says what it takes and whether failing costs for good, so two ways round compare on one card.
const odds = (o: CardOption) =>
  o.dc ? [ko.atLeast(o.dc), o.risk === 'high' ? ko.irreversible : null].filter(Boolean).join(' · ') : undefined;

// The sentence is already in the chat above, so the card asks and lists the answers, nothing more.
export function ClarifyCard({ card, onPick, onCancel }: { card: Card; onPick: (id: string) => void; onCancel: () => void }) {
  return (
    <Sheet title={card.question} onClose={onCancel}>
      {card.options.map((o) => <Choice key={o.id} label={o.label} sub={odds(o)} onPress={() => onPick(o.id)} />)}
    </Sheet>
  );
}
