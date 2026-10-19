import { useState } from 'react';
import { Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { PagedList } from '@/components/ui/PagedList';
import { ko } from '@/locale/ko';
import type { Button as Choice } from '@/services/types';

// Up to twelve growth options in the bottom bar left the scene one line per page; the bar holds two
// buttons and each opens its options as a paged list.
const GROUPS = [
  { prefix: 'grow:approach:', label: ko.growApproach },
  { prefix: 'grow:trait:', label: ko.growTrait },
];

export function Growth({ options, disabled, onPick }: { options: Choice[]; disabled: boolean; onPick: (id: string) => void }) {
  const [open, setOpen] = useState<number | null>(null);
  const groups = GROUPS.map((g) => ({ ...g, options: options.filter((o) => o.id.startsWith(g.prefix)) })).filter((g) => g.options.length);
  const chosen = open === null ? null : groups[open];
  return (
    <View className="gap-2 border-t border-border-default px-6 py-3">
      <Text accessibilityRole="header" className="font-sans-semibold text-body text-gold-fg">{ko.growthTitle}</Text>
      {groups.map((g, i) => <Button key={g.prefix} label={`${g.label} (${g.options.length})`} disabled={disabled} onPress={() => setOpen(i)} />)}
      {chosen ? (
        <Dialog title={chosen.label} onClose={() => setOpen(null)}>
          <PagedList entries={chosen.options.map((o) => ({ id: o.id, label: o.label }))} disabled={disabled}
            onSelect={(id) => { setOpen(null); onPick(id); }} />
        </Dialog>
      ) : null}
    </View>
  );
}
