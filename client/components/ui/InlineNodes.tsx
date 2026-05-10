import { Text } from 'react-native';

type Entry = [string, string | number];

export function InlineNodes({ entries }: { entries: Entry[] }) {
  return (
    <Text
      numberOfLines={1}
      className="font-mono-semibold text-panel text-fg-default"
      style={{ fontVariant: ['tabular-nums'] }}
    >
      {entries.map(([k, v]) => `${k} ${v}`).join(' · ')}
    </Text>
  );
}
