import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { Surface } from '@/components/ui';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Hero } from '@/logic/hero';
import type { GraphLevelUpChoice, GraphLevelUpGrowth } from '@/services/wire';

type GrowthChoice = {
  id: string;
  label: string;
  description?: string;
  growth: GraphLevelUpGrowth;
};

const CHOICES: GrowthChoice[] = [
  { id: 'max_hp', label: ko.level.maxHpChoice, growth: { kind: 'max_hp' } },
  { id: 'max_mp', label: ko.level.maxMpChoice, growth: { kind: 'max_mp' } },
];

const STAT_CHOICE_ORDER: Record<string, number> = {
  body: 0,
  agility: 1,
  mind: 2,
  presence: 3,
};

function growthChoiceRank(choice: GrowthChoice): number {
  const growth = choice.growth;
  if (growth.kind === 'stat') return STAT_CHOICE_ORDER[growth.stat] ?? 99;
  if (growth.kind === 'max_hp') return 4;
  if (growth.kind === 'max_mp') return 5;
  if (growth.kind === 'upgrade_skill') return 6;
  if (growth.kind === 'learn_skill') return 7;
  return 99;
}

function sortGrowthChoices(choices: GrowthChoice[]): GrowthChoice[] {
  return [...choices].sort((a, b) => growthChoiceRank(a) - growthChoiceRank(b));
}

type Props = {
  hero: Hero;
  choices?: GraphLevelUpChoice[];
  loading?: boolean;
  onCommit: (growth: GraphLevelUpGrowth) => void;
  onCancel: () => void;
};

export function LevelUpPrompt({ hero, choices = [], loading = false, onCommit, onCancel }: Props) {
  const growthChoices = React.useMemo(
    () => sortGrowthChoices(choices.length > 0 ? choices : loading ? [] : CHOICES),
    [choices, loading],
  );
  const [selectedId, setSelectedId] = React.useState<GrowthChoice['id']>(growthChoices[0]?.id ?? 'max_hp');
  React.useEffect(() => {
    setSelectedId(growthChoices[0]?.id ?? 'max_hp');
  }, [growthChoices]);
  const selected = growthChoices.find((choice) => choice.id === selectedId) ?? growthChoices[0];

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
            flexGrow: 0,
            flexBasis: '23.5%',
            minHeight: 36,
            borderRadius: 6,
            borderWidth: 1,
            alignItems: 'center',
            justifyContent: 'center',
            paddingHorizontal: 8,
            paddingVertical: 6,
          },
          style,
        ]}
      >
        <Text
          className="font-sans-semibold text-panel"
          numberOfLines={2}
          style={{ color: textColor, textAlign: 'center' }}
        >
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

      {loading ? (
        <Text className="font-sans text-caption text-fg-muted" style={{ marginBottom: 6 }}>
          {ko.level.loadingChoices}
        </Text>
      ) : null}

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {growthChoices.map(renderChoiceButton)}
      </View>

      {selected?.description ? (
        <Text className="font-sans text-caption text-fg-muted" style={{ marginTop: 6 }} numberOfLines={2}>
          {selected.description}
        </Text>
      ) : null}

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
          onPress={() => {
            if (selected) onCommit(selected.growth);
          }}
          disabled={!selected || loading}
          accessibilityRole="button"
          accessibilityLabel={ko.level.confirmAction}
          style={{
            flex: 1, height: 36, borderRadius: 6,
            alignItems: 'center', justifyContent: 'center',
            borderWidth: 1, borderColor: colors.accent.fg,
            backgroundColor: 'rgba(214,122,92,0.15)',
            opacity: selected && !loading ? 1 : 0.5,
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
