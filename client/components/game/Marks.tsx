import { Text, View } from 'react-native';

export function Marks({ marks }: { marks: string[] }) {
  if (!marks.length) return null;
  return (
    <View className="flex-row flex-wrap gap-1.5">
      {marks.map((m) => (
        <Text key={m} className="rounded-full bg-gold-muted px-2 font-sans text-chip text-gold-fg">{m}</Text>
      ))}
    </View>
  );
}
