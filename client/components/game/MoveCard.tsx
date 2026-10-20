import { Text } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Choice, Sheet } from '@/components/ui/Sheet';
import { ko } from '@/locale/ko';
import type { Card } from '@/services/types';

// A sentence that named its place gets one way to confirm; otherwise every way, the sentence's pick first in gold.
// Each says who comes along; one tap leaves.
export function MoveCard({ card, onPick, onCancel }: { card: Card; onPick: (id: string) => void; onCancel: () => void }) {
  if (card.options.length === 1) {
    const o = card.options[0];
    return (
      <Sheet title={ko.goTo(o.label)} icon="arrow" onClose={onCancel}>
        {o.effects?.length ? <Text className="font-sans text-panel text-fg-muted">{o.effects.join(' · ')}</Text> : null}
        <Button icon="arrow" label={ko.leave} onPress={() => onPick(o.id)} />
      </Sheet>
    );
  }
  return (
    <Sheet title={ko.whereTo} icon="arrow" onClose={onCancel}>
      {card.options.map((o) => (
        <Choice key={o.id} label={o.label} sub={o.effects?.length ? o.effects.join(' · ') : undefined}
          primary={o.id === card.selected} onPress={() => onPick(o.id)} />
      ))}
    </Sheet>
  );
}
