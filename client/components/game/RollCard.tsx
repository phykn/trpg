import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated, {
  useAnimatedStyle, useReducedMotion, useSharedValue, withSequence, withSpring, withTiming,
} from 'react-native-reanimated';

import { colors, fontFamily } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Frame } from '@/logic/reveal';
import type { Card, CardOption, Preview, StepRecord } from '@/services/types';
import { Boxes } from './Boxes';
import { Chips, signed } from './Chips';
import { Dice } from './Dice';
import { useDialog } from './useDialog';

const plain = (o: CardOption) => !o.id.includes('rely=');

function Banner({ result }: { result: string }) {
  const reduced = useReducedMotion();
  const scale = useSharedValue(reduced ? 1 : 0.6);
  useEffect(() => {
    if (!reduced) scale.value = withSequence(withTiming(1.12, { duration: 180 }), withSpring(1, { damping: 9 }));
  }, [reduced, scale]);
  const style = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const won = result === 'success';
  const color = won ? colors.gold.fg : colors.danger.fg;
  return (
    <Animated.Text accessibilityRole="alert" style={[{
      color, fontSize: 30, lineHeight: 40, fontFamily: fontFamily['sans-semibold'][0], letterSpacing: 4,
      textShadowColor: color, textShadowRadius: won ? 18 : 6, textShadowOffset: { width: 0, height: 0 },
    }, style]}>
      {ko.result[result]}
    </Animated.Text>
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
  const approach = p.mods.find((m) => m.kind === 'stat')?.label;
  const fill = target?.fill ?? 0;
  const own = step ? step.changes.findIndex((c) => c.kind === 'fill' && c.id === target?.id) : -1;
  const gained = frame && own >= 0 ? frame.boxes[own] ?? 0 : 0;
  const ref = useDialog(locked ? undefined : onCancel);
  const ring = high ? colors.danger.fg : colors.gold.fg;

  const reduced = useReducedMotion();
  const shake = useSharedValue(0);
  useEffect(() => {
    if (frame?.settled !== 'fail' || reduced) return;
    shake.value = withSequence(...[-8, 8, -5, 5, 0].map((x) => withTiming(x, { duration: 60 })));
  }, [frame?.settled, reduced, shake]);
  const shaken = useAnimatedStyle(() => ({ transform: [{ translateX: shake.value }] }));

  return (
    <Animated.View style={shaken}>
      <View ref={ref} accessibilityRole={'dialog' as never} aria-modal
        className="items-center gap-3 rounded-xl border bg-canvas-floating px-5 pb-4 pt-5"
        style={{ borderColor: high ? colors.danger.fg : colors.border.strong }}>
        <View className="flex-row items-center gap-2">
          <Text className="font-sans-semibold text-body text-fg-default">
            {[approach, target?.name].filter(Boolean).join(' · ')}
          </Text>
          {target?.boxes ? <Boxes fill={fill + gained} boxes={target.boxes} fit={0} size={10} /> : null}
        </View>
        <View className="items-center gap-1">
          <Text className="font-sans text-chip text-fg-muted">{ko.target}</Text>
          <View className="h-[76px] w-[76px] items-center justify-center rounded-full" style={{ borderWidth: 2, borderColor: ring }}>
            <Text className="font-mono-medium text-fg-default" style={{ fontSize: 34, lineHeight: 40 }}>{p.dc}</Text>
          </View>
          {high ? <Text className="font-sans-semibold text-chip text-danger-fg">{ko.highRisk}</Text> : null}
        </View>
        <Dice state={frame?.blocked ? 'gone' : step ? 'stopped' : rolling ? 'rolling' : 'ready'}
          values={frame ? frame.dice : [null, null]} label={ko.hold} onRelease={() => onRoll(pick)} />
        <View className="h-[40px] items-center justify-center">
          {frame?.settled ? <Banner result={frame.settled} /> : frame?.point != null ? (
            <Text className="font-mono-medium text-title text-fg-default">{ko.sum(frame.point)}</Text>
          ) : null}
        </View>
        {step && frame ? (
          <Chips chips={step.mods} decisive={frame.decisive} shown={frame.chips} />
        ) : (
          <View className="items-center gap-2">
            {fixed.length ? <Chips chips={fixed} /> : null}
            {card.options.length > 1 ? (
              <View className="flex-row flex-wrap justify-center" style={{ gap: 6 }}>
                {card.options.filter((o) => !plain(o)).map((o) => {
                  const chip = relyChip(o);
                  const on = o.id === pick;
                  return (
                    <Pressable key={o.id} accessibilityRole="checkbox" accessibilityState={{ checked: on, disabled: locked }}
                      disabled={locked} onPress={() => setPick(on ? none.id : o.id)}
                      className={`rounded-full border px-3 py-1 ${on ? 'border-gold-fg bg-accent-muted' : 'border-border-default'}`}>
                      <Text className={`font-sans text-panel ${on ? 'text-gold-fg' : 'text-fg-muted'}`}>
                        {o.label}{chip ? ` ${signed(chip.value)}` : ''}{o.note ? ` · ${o.note}` : ''}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            ) : null}
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
    </Animated.View>
  );
}
