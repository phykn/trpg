import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated, { useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';

import { colors, fontFamily } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Frame } from '@/logic/reveal';
import type { Card, CardOption, Chip, Preview, StepRecord } from '@/services/types';
import { Boxes } from './Boxes';
import { signed } from './Chips';
import { Dice } from './Dice';
import { useDialog } from './useDialog';

const plain = (o: CardOption) => !o.id.includes('rely=');

function Banner({ result }: { result: string }) {
  const reduced = useReducedMotion();
  const fade = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    if (!reduced) fade.value = withTiming(1, { duration: 400 });
  }, [reduced, fade]);
  const style = useAnimatedStyle(() => ({ opacity: fade.value }));
  return (
    <Animated.Text accessibilityRole="alert" style={[{
      color: result === 'success' ? colors.gold.fg : colors.danger.fg,
      fontSize: 24, lineHeight: 32, fontFamily: fontFamily['sans-semibold'][0], letterSpacing: 2,
    }, style]}>
      {ko.result[result]}
    </Animated.Text>
  );
}

function Mods({ mods, shown, decisive = [] }: { mods: Chip[]; shown?: number; decisive?: number[] }) {
  return (
    <View className="flex-row flex-wrap justify-center" style={{ columnGap: 10, rowGap: 2 }}>
      {mods.map((m, i) => {
        const key = decisive.includes(i);
        return (
          <Text key={`${m.label}${i}`} className={`text-panel ${key ? 'font-sans-semibold' : 'font-sans'}`}
            style={{ color: colors.chip[m.kind], opacity: shown !== undefined && i >= shown ? 0.35 : 1 }}>
            {m.label} {signed(m.value)}{key ? ` ${m.kind === 'hinder' ? ko.because : ko.thanks}` : ''}
          </Text>
        );
      })}
    </View>
  );
}

export function RollCard({ card, onRoll, onCancel, step, frame, rolling }: {
  card: Card; onRoll: (pick: string) => void; onCancel: () => void;
  step?: StepRecord; frame?: Frame; rolling?: boolean;
}) {
  const none = card.options.find(plain) ?? card.options[card.options.length - 1];
  const [pick, setPick] = useState(card.selected ?? none.id);
  const chosen = card.options.find((o) => o.id === pick) ?? none;
  const p = chosen.preview as Preview;
  const target = card.plan.step?.target;
  const high = p.risk === 'high';
  const locked = rolling || !!step;
  const relyChip = (o: CardOption) => o.preview?.mods.find((m) => m.kind === 'help' && m.label === o.label);
  const fixed = p.mods.filter((m) => m.value !== 0 && m.kind !== 'help');
  const fill = target?.fill ?? 0;
  const own = step ? step.changes.findIndex((c) => c.kind === 'fill' && c.id === target?.id) : -1;
  const gained = frame && own >= 0 ? frame.boxes[own] ?? 0 : 0;
  const ref = useDialog(locked ? undefined : onCancel);

  return (
    <View ref={ref} accessibilityRole={'dialog' as never} aria-modal
      className="items-center gap-3 rounded-xl border bg-canvas-floating px-5 pb-4 pt-5"
      style={{ borderColor: high ? colors.danger.fg : colors.border.strong }}>
      <View className="items-center gap-1">
        <Text className="text-center font-sans-semibold text-body text-fg-default">{card.plan.step?.label}</Text>
        {target?.boxes && target.boxes > 1 ? <Boxes fill={fill + gained} boxes={target.boxes} fit={0} size={10} /> : null}
      </View>
      <View className="items-center gap-1">
        <View className="h-[64px] w-[64px] items-center justify-center rounded-full"
          style={{ borderWidth: 1.5, borderColor: high ? colors.danger.fg : colors.border.strong }}>
          <Text className={`font-mono-medium ${high ? 'text-danger-fg' : 'text-fg-default'}`}
            style={{ fontSize: 28, lineHeight: 34 }}>{p.dc}</Text>
        </View>
        {high ? <Text className="font-sans text-chip text-danger-fg">{ko.highRisk}</Text> : null}
      </View>
      <Dice state={frame?.blocked ? 'gone' : step ? 'stopped' : rolling ? 'rolling' : 'ready'}
        values={frame ? frame.dice : [null, null]} label={ko.hold} onRelease={() => onRoll(pick)} />
      <View className="h-[32px] items-center justify-center">
        {frame?.settled ? <Banner result={frame.settled} /> : frame?.point != null ? (
          <Text className="font-mono-medium text-title text-fg-default">{frame.point}</Text>
        ) : null}
      </View>
      {step && frame ? (
        <Mods mods={step.mods} decisive={frame.decisive} shown={frame.chips} />
      ) : (
        <View className="items-center gap-2">
          {fixed.length ? <Mods mods={fixed} /> : null}
          {card.options.filter((o) => !plain(o)).map((o) => {
            const chip = relyChip(o);
            const on = o.id === pick;
            return (
              <Pressable key={o.id} accessibilityRole="checkbox" accessibilityState={{ checked: on, disabled: locked }}
                disabled={locked} onPress={() => setPick(on ? none.id : o.id)} className="flex-row items-center gap-2 py-1">
                <View className="h-3 w-3 rounded-sm border border-border-strong" style={on ? { backgroundColor: colors.fg.default } : null} />
                <Text className={`font-sans text-panel ${on ? 'text-fg-default' : 'text-fg-muted'}`}>
                  {o.label}{chip ? ` ${signed(chip.value)}` : ''}{o.note ? ` · ${o.note}` : ''}
                </Text>
              </Pressable>
            );
          })}
        </View>
      )}
      {frame?.blocked?.length ? (
        <Text className="font-sans-semibold text-title text-danger-fg">{frame.blocked.join(', ')}</Text>
      ) : null}
      {!locked ? (
        <Pressable accessibilityRole="button" onPress={onCancel} className="px-3 py-1">
          <Text className="font-sans text-panel text-fg-muted">{ko.cancel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
