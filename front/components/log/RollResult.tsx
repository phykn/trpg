import React from 'react';
import { View, Text } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';
import type { LogEntry } from '@/types/game';

type RollEntry = Extract<LogEntry, { kind: 'roll' }>;

function Cell({ k, v, flex = 1 }: { k: string; v: React.ReactNode; flex?: number }) {
  return (
    <View style={{ flex, flexDirection: 'row', alignItems: 'baseline', gap: 5 }}>
      <Text style={{
        ...typeStyle('meta', { letterSpacing: 1.2, fontWeight: '600' as const }),
        color: Theme.textFaint, fontFamily: Theme.fonts.monoSemibold, textTransform: 'uppercase',
      }}>{k}</Text>
      <Text style={{
        ...typeStyle('caption', { fontWeight: '600' as const }),
        color: Theme.text, fontFamily: Theme.fonts.monoSemibold, fontVariant: ['tabular-nums'],
      }}>{v}</Text>
    </View>
  );
}

export function RollResult({ entry }: { entry: RollEntry }) {
  const pass = entry.result === 'success';
  const color = pass ? Theme.good : Theme.bad;
  const total = entry.roll + entry.mod;
  const modStr = entry.mod >= 0 ? `+${entry.mod}` : `${entry.mod}`;

  return (
    <View style={{
      flexDirection: 'row', alignItems: 'center',
      backgroundColor: Theme.bgCard,
      borderWidth: 1, borderColor: Theme.border,
      borderLeftWidth: 3, borderLeftColor: color,
      borderRadius: Theme.radius.md,
      paddingVertical: Theme.space.md + 2, paddingHorizontal: Theme.space.md,
      gap: Theme.space.md,
    }}>
      <Text style={{
        ...typeStyle('meta', { letterSpacing: 1.4, fontWeight: '700' as const }),
        color, flexShrink: 0, textTransform: 'uppercase',
        fontFamily: Theme.fonts.sansBold,
      }}>{pass ? '성공' : '실패'}</Text>
      <View style={{ width: 1, height: 14, backgroundColor: Theme.border }} />
      <View style={{ flex: 1, flexDirection: 'row', alignItems: 'baseline', gap: Theme.space.md }}>
        <Cell k="판정" v={entry.check} flex={1} />
        <Cell k="난이도" v={entry.dc} flex={1} />
        <Cell k="결과"
          v={<><Text style={{ color: Theme.text }}>{entry.roll}</Text><Text style={{ color: Theme.textFaint }}>{modStr}</Text><Text>={total}</Text></>}
          flex={2}
        />
      </View>
    </View>
  );
}
