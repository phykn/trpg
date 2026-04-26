import React from 'react';
import { View, Text } from 'react-native';

type Entry = [string, string | number | React.ReactNode];

export function InlineNodes({ entries, weights }: {
  entries: Entry[];
  weights?: number[];
}) {
  return (
    <View className="flex-1 min-w-0 flex-row gap-1 items-center h-5">
      {entries.map(([k, v], i) => (
        <View
          key={i}
          className="flex-row items-center justify-start gap-1 min-w-0"
          style={{ flex: weights?.[i] ?? 1 }}
        >
          <Text
            numberOfLines={1}
            className="font-mono-semibold text-panel text-fg-subtle uppercase"
            style={{ letterSpacing: 1.2, fontVariant: ['tabular-nums'] }}
          >
            {k}
          </Text>
          {typeof v === 'string' || typeof v === 'number' ? (
            <Text
              numberOfLines={1}
              className="font-mono-semibold text-panel text-fg-default"
              style={{ fontVariant: ['tabular-nums'] }}
            >
              {String(v)}
            </Text>
          ) : (
            v
          )}
        </View>
      ))}
    </View>
  );
}
