import React from 'react';
import { Pressable, Text, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { colors } from '@/design/tokens';
import { Surface, signed } from '@/components/ui';
import { ko } from '@/locale/ko';
import type { PendingCheck } from '@/services/wire';

const STOP_BUTTON_DELAY_MS = 2000;

type Zone = 'crit-fail' | 'fail' | 'partial' | 'success' | 'crit-success';

function zoneFor(d: number, threshold: number): Zone {
  if (d === 1) return 'crit-fail';
  if (d === 20) return 'crit-success';
  if (d < threshold) return 'fail';
  if (d === threshold) return 'partial';
  return 'success';
}

const ZONE_BG: Record<Zone, string> = {
  'crit-fail':    colors.danger.fg,
  fail:           'rgba(181,83,74,0.16)',
  partial:        colors.exp.fg,
  success:        'rgba(123,140,112,0.16)',
  'crit-success': colors.success.fg,
};

const ZONE_FG: Record<Zone, string> = {
  'crit-fail':    colors.fg['on-emphasis'],
  fail:           colors.danger.fg,
  partial:        colors.fg['on-emphasis'],
  success:        colors.success.fg,
  'crit-success': colors.fg['on-emphasis'],
};

export function RollPrompt({
  pending,
  onRoll,
  onStop,
  rolling,
}: {
  pending: PendingCheck;
  onRoll: () => void;
  onStop: () => void;
  rolling: boolean;
}) {
  const requiredDice = Math.min(20, Math.max(2, pending.required_roll - pending.mod));
  const statBonus = pending.dc - pending.required_roll;
  const dice = Array.from({ length: 20 }, (_, i) => i + 1);

  const showStat = statBonus !== 0;
  const showMod = pending.mod !== 0;

  // Stop button is delayed so a fast roll never flashes through it.
  const [showStop, setShowStop] = React.useState(false);
  React.useEffect(() => {
    if (!rolling) {
      setShowStop(false);
      return;
    }
    const t = setTimeout(() => setShowStop(true), STOP_BUTTON_DELAY_MS);
    return () => clearTimeout(t);
  }, [rolling]);

  return (
    <Surface className="mx-5 mt-1.5 px-3 py-2.5">
      {pending.reason && (
        <Text
          className="font-sans-medium text-caption text-fg-subtle mb-2"
          style={{ letterSpacing: 0.6 }}
        >
          {pending.reason}
        </Text>
      )}

      {/* Header — stat label + DC badge */}
      <View className="flex-row items-baseline justify-between mb-2">
        <View className="flex-row items-baseline gap-1.5">
          <Text
            className="font-sans-semibold text-panel text-fg-default"
            style={{ letterSpacing: 1.2 }}
          >
            {pending.stat_label}
          </Text>
          <Text
            className="font-sans text-caption text-fg-subtle"
            style={{ letterSpacing: 0.6 }}
          >
            {ko.roll.check}
          </Text>
        </View>
        <View className="flex-row items-baseline gap-1">
          <Text
            className="font-sans text-caption text-fg-subtle"
            style={{ letterSpacing: 0.6 }}
          >
            {ko.roll.difficulty}
          </Text>
          <Text
            className="font-mono-semibold text-panel text-fg-default"
            style={{ fontVariant: ['tabular-nums'] }}
          >
            {pending.dc}
          </Text>
        </View>
      </View>

      {/* Dice strip — 20 cells colored by outcome zone */}
      <View className="flex-row" style={{ gap: 2 }}>
        {dice.map((d) => {
          const zone = zoneFor(d, requiredDice);
          const isThreshold = d === requiredDice;
          return (
            <View
              key={d}
              className="flex-1 items-center justify-center rounded-sm"
              style={{
                backgroundColor: ZONE_BG[zone],
                height: 28,
                borderWidth: isThreshold ? 1.5 : 0,
                borderColor: colors.accent.fg,
              }}
            >
              <Text
                className="font-mono-semibold"
                style={{
                  color: ZONE_FG[zone],
                  fontSize: 10,
                  fontVariant: ['tabular-nums'],
                  letterSpacing: 0,
                }}
              >
                {d}
              </Text>
            </View>
          );
        })}
      </View>

      {/* Marker row — triangle + required label aligned to threshold cell */}
      <View className="flex-row mt-1" style={{ gap: 2 }}>
        {dice.map((d) => (
          <View key={d} className="flex-1 items-center">
            {d === requiredDice && (
              <Text
                className="font-mono-semibold"
                style={{ color: colors.accent.fg, fontSize: 8, lineHeight: 10 }}
              >
                ▲
              </Text>
            )}
          </View>
        ))}
      </View>

      <View className="flex-row items-baseline justify-center gap-1.5 mt-0.5">
        <Text
          className="font-sans-semibold text-caption text-fg-subtle"
          style={{ letterSpacing: 1.2 }}
        >
          {ko.roll.required}
        </Text>
        <Text
          className="font-mono-semibold text-title"
          style={{ color: colors.accent.fg, fontVariant: ['tabular-nums'] }}
        >
          {requiredDice}
        </Text>
        <Text
          className="font-sans text-caption text-fg-muted"
          style={{ letterSpacing: 0.6 }}
        >
          {ko.roll.orMore}
        </Text>
      </View>

      {/* Bonus chain — only when there's a bonus to explain */}
      {(showStat || showMod) && (
        <View
          className="flex-row items-baseline justify-center flex-wrap mt-2 pt-2 border-t border-border-default"
          style={{ gap: 10 }}
        >
          {showStat && (
            <View className="flex-row items-baseline gap-1">
              <Text
                className="font-sans text-caption text-fg-subtle"
                style={{ letterSpacing: 0.6 }}
              >
                {pending.stat_label}
              </Text>
              <Text
                className="font-mono text-caption text-fg-muted"
                style={{ fontVariant: ['tabular-nums'] }}
              >
                {pending.stat_value}
              </Text>
              <Text
                className="font-mono text-caption text-fg-subtle"
                style={{ fontVariant: ['tabular-nums'] }}
              >
                →
              </Text>
              <Text
                className="font-sans text-caption text-fg-subtle"
                style={{ letterSpacing: 0.6 }}
              >
                {ko.roll.abilityBonus}
              </Text>
              <Text
                className="font-mono-semibold text-caption"
                style={{ color: colors.accent.fg, fontVariant: ['tabular-nums'] }}
              >
                {signed(statBonus)}
              </Text>
            </View>
          )}
          {showMod && (
            <View className="flex-row items-baseline gap-1">
              {/* Provisional branch: long-term wire should carry `mod_label` from server (spec §5.3 미정 항목). */}
              <Text
                className="font-sans text-caption text-fg-subtle"
                style={{ letterSpacing: 0.6 }}
              >
                {pending.kind === 'recruit' ? ko.roll.affinity : ko.roll.liking}
              </Text>
              <Text
                className="font-mono-semibold text-caption"
                style={{ color: colors.accent.fg, fontVariant: ['tabular-nums'] }}
              >
                {signed(pending.mod)}
              </Text>
            </View>
          )}
        </View>
      )}

      {rolling && showStop ? (
        <Pressable
          onPress={onStop}
          accessibilityRole="button"
          accessibilityLabel={ko.roll.stopLabel}
          testID="roll-stop-button"
          className="flex-row items-center justify-center gap-2 mt-3 h-10 rounded-md bg-accent-fg active:opacity-80"
        >
          <View
            style={{
              width: 12,
              height: 12,
              borderRadius: 2,
              backgroundColor: colors.canvas.subtle,
            }}
          />
          <Text
            className="font-sans-semibold text-title"
            style={{ letterSpacing: 1.2, color: colors.canvas.subtle }}
          >
            {ko.roll.halt}
          </Text>
        </Pressable>
      ) : (
        <Pressable
          onPress={rolling ? undefined : onRoll}
          disabled={rolling}
          accessibilityRole="button"
          accessibilityLabel={rolling ? ko.roll.rollingLabel : ko.roll.rollLabel}
          accessibilityState={{ disabled: rolling }}
          testID="roll-button"
          className={`flex-row items-center justify-center gap-2 mt-3 h-10 rounded-md border ${
            rolling
              ? 'bg-transparent border-border-default'
              : 'bg-accent-muted border-accent-fg active:opacity-80'
          }`}
          style={{ opacity: rolling ? 0.55 : 1 }}
        >
          <Svg width={16} height={16} viewBox="0 0 24 24" fill="none">
            <Path
              d="M12 2.5L20.5 7.5V16.5L12 21.5L3.5 16.5V7.5L12 2.5Z"
              stroke={rolling ? colors.fg.subtle : colors.accent.fg}
              strokeWidth={1.6}
              strokeLinejoin="round"
            />
            <Path
              d="M12 2.5L12 21.5M3.5 7.5L20.5 16.5M20.5 7.5L3.5 16.5"
              stroke={rolling ? colors.fg.subtle : colors.accent.fg}
              strokeWidth={0.8}
              opacity={0.5}
            />
          </Svg>
          <Text
            className={`font-sans-semibold text-title ${
              rolling ? 'text-fg-subtle' : 'text-accent-fg'
            }`}
            style={{ letterSpacing: 1.2 }}
          >
            {rolling ? ko.roll.rolling : ko.action.roll}
          </Text>
        </Pressable>
      )}
    </Surface>
  );
}
