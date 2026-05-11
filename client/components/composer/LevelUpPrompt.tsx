import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { Surface } from '@/components/ui';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Hero } from '@/logic/hero';
import type { GraphLevelUpGrowth } from '@/services/wire';

type GrowthChoice = {
  id: 'max_hp' | 'max_mp';
  label: string;
  growth: GraphLevelUpGrowth;
};

const CHOICES: GrowthChoice[] = [
  { id: 'max_hp', label: ko.level.maxHpChoice, growth: { kind: 'max_hp' } },
  { id: 'max_mp', label: ko.level.maxMpChoice, growth: { kind: 'max_mp' } },
];

type Props = {
  hero: Hero;
  onCommit: (growth: GraphLevelUpGrowth) => void;
  onCancel: () => void;
};

export function LevelUpPrompt({ hero, onCommit, onCancel }: Props) {
  const [selectedId, setSelectedId] = React.useState<GrowthChoice['id']>('max_hp');
  const selected = CHOICES.find((choice) => choice.id === selectedId) ?? CHOICES[0];

  const renderChoiceButton = (choice: GrowthChoice) => {
    const active = selectedId === choice.id;
    const style = active
      ? { backgroundColor: colors.accent.fg, borderColor: colors.accent.fg }
      : { borderColor: colors.border.default };
    const textColor = active ? colors.canvas.default : colors.fg.default;

    return (
      <Pressable
        key={choice.id}
        testID={`level-growth-${choice.id}`}
        onPress={() => { setSelectedId(choice.id); }}
        accessibilityRole="button"
        accessibilityLabel={choice.label}
        style={[
          {
            flex: 1,
            height: 34,
            borderRadius: 6,
            borderWidth: 1,
            alignItems: 'center',
            justifyContent: 'center',
          },
          style,
        ]}
      >
        <Text className="font-sans-semibold text-panel" style={{ color: textColor }}>
          {choice.label}
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

      <View style={{ flexDirection: 'row', gap: 6 }}>
        {CHOICES.map(renderChoiceButton)}
      </View>

      <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
        <Pressable
          testID="level-cancel"
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
          testID="level-confirm"
          onPress={() => onCommit(selected.growth)}
          accessibilityRole="button"
          accessibilityLabel={ko.level.confirmAction}
          style={{
            flex: 1, height: 36, borderRadius: 6,
            alignItems: 'center', justifyContent: 'center',
            borderWidth: 1, borderColor: colors.accent.fg,
            backgroundColor: 'rgba(214,122,92,0.15)',
          }}
        >
          <Text className="font-sans-semibold text-title" style={{ color: colors.accent.fg, letterSpacing: 1.2 }}>
            {ko.level.title}
          </Text>
        </Pressable>
      </View>
    </Surface>
  );
}
