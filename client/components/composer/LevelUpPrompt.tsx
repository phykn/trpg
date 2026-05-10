import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { Surface } from '@/components/ui';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Hero } from '@/logic/hero';
import type { GraphStatKey } from '@/services/wire';

const GRAPH_STAT_ROWS: [GraphStatKey, GraphStatKey][] = [
  ['body', 'agility'],
  ['mind', 'presence'],
];

const STAT_CAP = 20;

type Props = {
  hero: Hero;
  onCommit: (stat_up: GraphStatKey) => void;
  onCancel: () => void;
};

export function LevelUpPrompt({ hero, onCommit, onCancel }: Props) {
  const [statUp, setStatUp] = React.useState<GraphStatKey | null>(null);

  const statValueOf = (k: GraphStatKey): number => {
    const row = hero.stats.find((s) => s.label === ko.ability[k]);
    return row ? row.value : 0;
  };

  const isStatDisabled = (k: GraphStatKey): boolean => statValueOf(k) >= STAT_CAP;

  const canCommit = statUp !== null;

  const renderStatButton = (k: GraphStatKey) => {
    const isUp = statUp === k;
    const disabled = isStatDisabled(k);
    const baseValue = statValueOf(k);
    const previewValue = isUp ? baseValue + 1 : baseValue;

    let style: object = { borderWidth: 1, borderColor: colors.border.default };
    let textColor = colors.fg.default;
    if (isUp) {
      style = { backgroundColor: colors.accent.fg };
      textColor = colors.canvas.default;
    }
    if (disabled && !isUp) {
      style = { ...style, opacity: 0.4 };
    }

    return (
      <Pressable
        key={k}
        onPress={disabled ? undefined : () => { setStatUp(k); }}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={`${ko.ability[k]} ${ko.level.raiseSuffix}`}
        style={[
          { flex: 1, paddingVertical: 6, paddingHorizontal: 4, borderRadius: 3, alignItems: 'center', justifyContent: 'center' },
          style,
        ]}
      >
        <Text className="font-sans-medium" style={{ color: textColor, fontSize: 11 }}>
          {ko.ability[k]} <Text style={{ fontVariant: ['tabular-nums'] }}>{previewValue}</Text>
        </Text>
      </Pressable>
    );
  };

  return (
    <Surface className="mx-5 mt-1.5 px-3 py-2.5">
      <View className="flex-row items-baseline justify-between mb-2">
        <View className="flex-row items-baseline gap-1.5">
          <Text className="font-sans-semibold text-panel text-fg-default" style={{ letterSpacing: 1.2 }}>
            {ko.level.title}
          </Text>
          <Text className="font-sans text-caption text-fg-subtle" style={{ letterSpacing: 0.6 }}>
            {hero.level} → {hero.level + 1}
          </Text>
        </View>
        <Text className="font-sans text-caption text-fg-muted">{ko.level.permanent}</Text>
      </View>

      <View style={{ gap: 3 }}>
        {GRAPH_STAT_ROWS.map(([a, b]) => (
          <View key={a + b} style={{ flexDirection: 'row', gap: 3 }}>
            {renderStatButton(a)}
            {renderStatButton(b)}
          </View>
        ))}
      </View>

      <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
        <Pressable
          onPress={onCancel}
          accessibilityRole="button"
          accessibilityLabel={ko.level.cancelAction}
          style={{
            flex: 1, height: 36, borderRadius: 6,
            alignItems: 'center', justifyContent: 'center',
            borderWidth: 1, borderColor: colors.border.default,
          }}
        >
          <Text className="font-sans-medium text-title" style={{ color: colors.fg.default, letterSpacing: 1.2 }}>
            {ko.level.cancel}
          </Text>
        </Pressable>
        <Pressable
          onPress={canCommit ? () => onCommit(statUp!) : undefined}
          disabled={!canCommit}
          accessibilityRole="button"
          accessibilityLabel={ko.level.confirmAction}
          style={[
            {
              flex: 1, height: 36, borderRadius: 6,
              alignItems: 'center', justifyContent: 'center',
              borderWidth: 1, borderColor: colors.accent.fg,
              backgroundColor: 'rgba(214,122,92,0.15)',
            },
            !canCommit ? { opacity: 0.55 } : null,
          ]}
        >
          <Text className="font-sans-semibold text-title" style={{ color: colors.accent.fg, letterSpacing: 1.2 }}>
            ✦ {ko.level.title}
          </Text>
        </Pressable>
      </View>
    </Surface>
  );
}
