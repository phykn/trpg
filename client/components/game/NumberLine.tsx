import { Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import type { GameView } from '@/services/types';

/** The scale 1–16 with the result bands, and the dot at the running total (ui.md 4.5 beats 2–4). */
export function NumberLine({ bands, point, settled }: { bands: GameView['bands']; point: number | null; settled: string | null }) {
  const span = bands.max - bands.min + 1;
  const left = (v: number) => `${((Math.min(Math.max(v, bands.min), bands.max) - bands.min + 0.5) / span) * 100}%` as const;
  const zones = [
    { k: 'fail', from: bands.min, to: bands.mixed - 1 },
    { k: 'mixed', from: bands.mixed, to: bands.success - 1 },
    { k: 'success', from: bands.success, to: bands.max },
  ] as const;
  return (
    <View className="h-9 justify-center">
      <View className="h-3 flex-row overflow-hidden rounded-sm">
        {zones.map((z) => (
          <View key={z.k} style={{
            flex: z.to - z.from + 1, backgroundColor: colors.band[z.k],
            opacity: settled && settled !== z.k ? 0.35 : 1,
          }} />
        ))}
      </View>
      {point !== null ? (
        <View className="absolute items-center" style={{ left: left(point), marginLeft: -12, width: 24, top: 0 }}>
          <View className="h-4 w-4 rounded-full bg-gold-fg" />
          <Text className="font-mono-medium text-chip text-fg-default">{point}</Text>
        </View>
      ) : null}
    </View>
  );
}
