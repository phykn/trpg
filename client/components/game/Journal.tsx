import { useState } from 'react';
import { View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { PagedList } from '@/components/ui/PagedList';
import { Reader } from '@/components/ui/Reader';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

export function Journal({ view }: { view: GameView }) {
  const [open, setOpen] = useState<number | null>(null);
  const entries = [...view.journal].reverse();
  const chosen = entries.find((e) => e.n === open);
  if (chosen) {
    const text = [chosen.input, chosen.lines.join('\n'), chosen.narration ?? ''].filter(Boolean).join('\n\n');
    return (
      <View className="flex-1 min-h-0 gap-4">
        <Button label={ko.back} onPress={() => setOpen(null)} />
        <Reader text={text || ko.noEntries} />
      </View>
    );
  }
  return <PagedList entries={entries.map((e) => ({ id: String(e.n), label: e.input || ko.turn(e.n), meta: [ko.turn(e.n), e.lines[0]].filter(Boolean).join(' · ') }))} onSelect={(id) => setOpen(Number(id))} />;
}
