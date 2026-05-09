import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { Surface } from '@/components/ui';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Hero } from '@/logic/hero';
import type {
  GraphStatKey,
  LevelUpStatKey,
  RuntimeMode,
  SkillCandidate,
  StatKey,
} from '@/services/wire';

const LEGACY_STAT_ROWS: [StatKey, StatKey][] = [
  ['STR', 'CHA'],
  ['DEX', 'WIS'],
  ['CON', 'INT'],
];

const GRAPH_STAT_ROWS: [GraphStatKey, GraphStatKey][] = [
  ['body', 'agility'],
  ['mind', 'presence'],
];

const LEGACY_STAT_PAIRED_DOWN: Record<StatKey, StatKey> = {
  STR: 'CHA', CHA: 'STR', DEX: 'WIS', WIS: 'DEX', CON: 'INT', INT: 'CON',
};

const STAT_CAP = 20;
const STAT_FLOOR = 0;

type Props = {
  hero: Hero;
  mode: RuntimeMode;
  candidates: SkillCandidate[] | null; // null = loading
  onCommit: (stat_up: LevelUpStatKey, skill_id: string | null) => void;
  onCancel: () => void;
};

export function LevelUpPrompt({ hero, mode, candidates, onCommit, onCancel }: Props) {
  const [statUp, setStatUp] = React.useState<LevelUpStatKey | null>(null);
  const [skillId, setSkillId] = React.useState<string | null>(null);
  const statRows: [LevelUpStatKey, LevelUpStatKey][] = mode === 'graph'
    ? GRAPH_STAT_ROWS
    : LEGACY_STAT_ROWS;

  const statValueOf = (k: LevelUpStatKey): number => {
    const row = hero.stats.find((s) => s.label === ko.ability[k]);
    return row ? row.value : 0;
  };

  const isStatDisabled = (k: LevelUpStatKey): boolean => {
    if (mode === 'graph') return statValueOf(k) >= STAT_CAP;
    const pairedDown = LEGACY_STAT_PAIRED_DOWN[k as StatKey];
    return statValueOf(k) >= STAT_CAP || statValueOf(pairedDown) <= STAT_FLOOR;
  };

  const skillRequired = candidates !== null && candidates.length > 0;
  const canCommit = statUp !== null && (!skillRequired || skillId !== null);

  const renderStatButton = (k: LevelUpStatKey) => {
    const isUp = statUp === k;
    const pairedDown = mode === 'graph' ? null : LEGACY_STAT_PAIRED_DOWN[k as StatKey];
    const isPairedDown = pairedDown !== null && statUp === pairedDown;
    const disabled = isStatDisabled(k);
    const baseValue = statValueOf(k);
    const previewValue = isUp ? baseValue + 1 : isPairedDown ? baseValue - 1 : baseValue;

    let style: object = { borderWidth: 1, borderColor: colors.border.default };
    let textColor = colors.fg.default;
    if (isUp) {
      style = { backgroundColor: colors.accent.fg };
      textColor = colors.canvas.default;
    } else if (isPairedDown) {
      style = { borderWidth: 1, borderColor: colors.danger.fg, backgroundColor: 'rgba(181,83,74,0.18)' };
      textColor = colors.danger.fg;
    }
    if (disabled && !isUp && !isPairedDown) {
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

  const renderSkillCard = (c: SkillCandidate) => {
    const isSelected = skillId === c.id;
    return (
      <Pressable
        key={c.id}
        onPress={() => setSkillId(c.id)}
        accessibilityRole="button"
        accessibilityLabel={`${ko.level.skillPrefix} ${c.name}`}
        style={[
          { paddingVertical: 6, paddingHorizontal: 8, borderRadius: 3 },
          isSelected
            ? { backgroundColor: colors.accent.fg }
            : { borderWidth: 1, borderColor: colors.border.default },
        ]}
      >
        <Text
          className="font-sans-medium"
          style={{ color: isSelected ? colors.canvas.default : colors.fg.default, fontSize: 11 }}
        >
          {c.name}
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

      <View style={{ flexDirection: 'row', gap: 8 }}>
        {/* Left column — stat choices */}
        <View style={{ flex: 1, gap: 3 }}>
          {statRows.map(([a, b]) => (
            <View key={a + b} style={{ flexDirection: 'row', gap: 3 }}>
              {renderStatButton(a)}
              {renderStatButton(b)}
            </View>
          ))}
        </View>

        {/* Right column — skill candidates */}
        <View style={{ flex: 1, gap: 3 }}>
          {candidates === null
            ? [0, 1, 2].map((i) => (
                <View
                  key={i}
                  style={{
                    paddingVertical: 6, paddingHorizontal: 8, borderRadius: 3,
                    borderWidth: 1, borderColor: colors.border.default, opacity: 0.4,
                  }}
                >
                  <Text className="font-sans text-caption text-fg-subtle">{ko.empty.loadingSkill}</Text>
                </View>
              ))
            : candidates.length === 0
            ? <Text className="font-sans text-caption text-fg-subtle">{ko.empty.noSkillCandidates}</Text>
            : candidates.map(renderSkillCard)}
        </View>
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
          onPress={canCommit ? () => onCommit(statUp!, skillId) : undefined}
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
