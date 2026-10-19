import { Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Chip as ChipT } from '@/services/types';

export const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : '±0');

export function Chip({ chip, small, mark, dim }: { chip: ChipT; small?: boolean; mark?: boolean; dim?: boolean }) {
  const color = colors.chip[chip.kind];
  return (
    <View className="flex-row items-center rounded-full px-2" style={{
      borderWidth: mark ? 2 : 1, borderColor: color, opacity: dim ? 0.35 : 1, paddingVertical: 1,
    }}>
      <Text className={`font-sans ${small ? 'text-chip' : 'text-panel'}`} style={{ color }}>
        {chip.label} {signed(chip.value)}{mark ? ` ${chip.kind === 'hinder' ? ko.because : ko.thanks}` : ''}
      </Text>
    </View>
  );
}

export function Chips({ chips, small, decisive = [], shown }: {
  chips: ChipT[]; small?: boolean; decisive?: number[]; shown?: number;
}) {
  return (
    <View className="flex-row flex-wrap" style={{ gap: 4 }}>
      {chips.map((c, i) => (
        <Chip key={`${c.label}${i}`} chip={c} small={small} mark={decisive.includes(i)}
          dim={shown !== undefined && i >= shown} />
      ))}
    </View>
  );
}
