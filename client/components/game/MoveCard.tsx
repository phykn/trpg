import { Choice, Sheet } from '@/components/ui/Sheet';
import { ko } from '@/locale/ko';
import type { Card } from '@/services/types';

// The way the sentence chose comes first in gold, each way saying who comes along; one tap leaves.
export function MoveCard({ card, onPick, onCancel }: { card: Card; onPick: (id: string) => void; onCancel: () => void }) {
  return (
    <Sheet title={ko.whereTo} icon="arrow" onClose={onCancel}>
      {card.options.map((o) => (
        <Choice key={o.id} label={o.label} sub={o.effects?.length ? o.effects.join(' · ') : undefined}
          primary={o.id === card.selected} onPress={() => onPick(o.id)} />
      ))}
    </Sheet>
  );
}
