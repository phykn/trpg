import { ScrollView, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import type { Line } from '@/services/types';
import { Marks } from './Marks';

// One notebook line with what can be done with it: presenting, using, betting.
export function LineSheet({ line, locked, onAct, onClose }: {
  line: Line; locked: boolean; onAct: (act: string) => void; onClose: () => void;
}) {
  return (
    <Sheet onClose={onClose}>
      <ScrollView className="max-h-80" contentContainerClassName="gap-3">
        <Text className={`font-serif-body text-body text-fg-default ${line.struck ? 'line-through opacity-60' : ''}`}>{line.text}</Text>
        <Marks marks={line.marks} />
        <View className="gap-2">
          {line.acts.map((a) => <Button key={a.id} tone="secondary" label={a.label} disabled={locked} onPress={() => onAct(a.id)} />)}
        </View>
      </ScrollView>
    </Sheet>
  );
}
