import { Pressable, ScrollView, Text, View } from 'react-native';

import { Button, pressed } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import type { Line } from '@/services/types';
import { Marks } from './Marks';

const struck = (line: Line) => (line.struck ? 'line-through opacity-60' : '');

// One notebook line with what can be done with it: presenting, using, betting. A person's line gathers what they said.
export function LineSheet({ line, about, locked, onAct, onLine, onClose }: {
  line: Line; about: Line[]; locked: boolean; onAct: (act: string) => void; onLine: (id: number) => void; onClose: () => void;
}) {
  return (
    <Sheet onClose={onClose}>
      <ScrollView className="max-h-96" contentContainerClassName="gap-3">
        <View className="gap-1">
          <Text className={`font-serif-body text-body text-fg-default ${struck(line)}`}>{line.text}</Text>
          {line.intro ? <Text className="font-sans text-chip text-fg-muted">{line.intro}</Text> : null}
        </View>
        <Marks marks={line.marks} />
        {about.length ? (
          <View className="gap-1.5">
            {about.map((l) => (
              <Pressable key={l.id} accessibilityRole="button" onPress={() => onLine(l.id)} style={pressed}
                className="gap-1 rounded-xl border border-border-default px-3 py-2">
                <Text className={`font-sans text-chip text-fg-default ${struck(l)}`}>{l.text}</Text>
                <Marks marks={l.marks} />
              </Pressable>
            ))}
          </View>
        ) : null}
        <View className="gap-2">
          {line.acts.map((a) => <Button key={a.id} tone="secondary" label={a.label} disabled={locked} onPress={() => onAct(a.id)} />)}
        </View>
      </ScrollView>
    </Sheet>
  );
}
