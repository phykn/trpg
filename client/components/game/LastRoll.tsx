import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { StepRecord } from '@/services/types';
import { Chip } from './Chips';

const FACE = ['', '⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];

/** The last roll's total, result and decisive chips, until the next roll (ui.md 4.5 beat 7). */
export function LastRoll({ step }: { step: StepRecord | null }) {
  if (!step?.roll) return <View className="h-5" />;
  return (
    <View className="flex-row flex-wrap items-center gap-2 px-4" style={{ minHeight: 20 }}>
      <Text className="font-mono-medium text-panel text-fg-default">
        {FACE[step.roll.d1]}{FACE[step.roll.d2]} {step.total}
      </Text>
      <Text className="font-sans-semibold text-panel text-gold-fg">{ko.result[step.result]}</Text>
      {step.decisive.map((i) => step.mods[i] ? <Chip key={i} chip={step.mods[i]} small mark /> : null)}
    </View>
  );
}
