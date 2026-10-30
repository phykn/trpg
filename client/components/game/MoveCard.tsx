import { Text } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Choice, Sheet } from '@/components/ui/Sheet';
import { ko } from '@/locale/ko';
import type { Card } from '@/services/types';

// A sentence that named its place gets one way to confirm; otherwise every way, the sentence's pick first in gold.
// Each says who comes along; one tap leaves. Going with someone here asks them first, as its own option.
export function MoveCard({ card, onPick, onCancel }: { card: Card; onPick: (id: string) => void; onCancel: () => void }) {
  const first = card.options[0];
  if (card.options.every((o) => o.label === first.label)) {
    return (
      <Sheet title={ko.goTo(first.label)} icon="arrow" onClose={onCancel}>
        {first.effects?.length ? <Text className="font-sans text-panel text-fg-muted">{first.effects.join(' · ')}</Text> : null}
        {card.options.map((o) => (
          <Button key={o.id} icon="arrow" label={o.with ? ko.leaveWith(o.with) : ko.leave}
            tone={o.id === (card.selected ?? first.id) ? 'primary' : 'secondary'} onPress={() => onPick(o.id)} />
        ))}
      </Sheet>
    );
  }
  return (
    <Sheet title={ko.whereTo} icon="arrow" onClose={onCancel}>
      {card.options.map((o) => (
        <Choice key={o.id} label={o.with ? `${o.label} · ${ko.leaveWith(o.with)}` : o.label}
          sub={o.effects?.length ? o.effects.join(' · ') : undefined}
          primary={o.id === card.selected} onPress={() => onPick(o.id)} />
      ))}
    </Sheet>
  );
}
