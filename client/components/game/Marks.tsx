import { Text, View } from 'react-native';

import { text } from '@/design/ui';

export function Marks({ marks }: { marks: string[] }) {
  if (!marks.length) return null;
  return (
    <View className="flex-row flex-wrap gap-1.5">
      {marks.map((m) => <Text key={m} className={text({ kind: 'mark' })}>{m}</Text>)}
    </View>
  );
}
