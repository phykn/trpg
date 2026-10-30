import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated, {
  Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withSequence, withTiming,
} from 'react-native-reanimated';

import { IconButton, pressed } from '@/components/ui/Button';
import { Notice, Resend } from '@/components/ui/Notice';
import { useDialog } from '@/components/ui/useDialog';
import { colors, fontFamily, motion } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Frame } from '@/logic/reveal';
import type { Card, CardOption, Chip, Preview, StepRecord } from '@/services/types';
import { Boxes } from './Boxes';
import { Dice } from './Dice';

const plain = (o: CardOption) => !o.id.includes('rely=');
const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : '±0');
const ease = Easing.out(Easing.cubic);

// The target number; once the roll settles it takes the result's colour, and a success sends out one soft ring.
function Target({ dc, high, result }: { dc: number; high: boolean; result: string | null }) {
  const reduced = useReducedMotion();
  const wave = useSharedValue(0);
  useEffect(() => {
    if (result === 'success' && !reduced) wave.value = withTiming(1, { duration: motion.ripple, easing: ease });
  }, [result, reduced, wave]);
  const ripple = useAnimatedStyle(() => ({ opacity: 0.5 * (1 - wave.value) * (wave.value > 0 ? 1 : 0), transform: [{ scale: 1 + 0.6 * wave.value }] }));
  const ring = result === 'success' ? colors.gold.fg : result === 'fail' || high ? colors.danger.fg : colors.border.strong;
  return (
    <View className="h-16 w-16 items-center justify-center">
      <Animated.View style={[{
        position: 'absolute', width: 64, height: 64, borderRadius: 32, borderWidth: 2, borderColor: colors.gold.fg,
      }, ripple]} />
      <View accessibilityLabel={high ? ko.highRisk : undefined} className="h-16 w-16 items-center justify-center rounded-full"
        style={{ borderWidth: result ? 2 : 1.5, borderColor: ring, backgroundColor: result === 'success' ? colors.gold.muted : 'transparent' }}>
        <Text className="font-mono-medium" style={{ fontSize: 28, lineHeight: 34, color: high && !result ? colors.danger.fg : colors.fg.default }}>{dc}</Text>
      </View>
    </View>
  );
}

// The result lands like a stamp: big, then down past its size and back (ui.md 4.5).
function Verdict({ result }: { result: string }) {
  const reduced = useReducedMotion();
  const t = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    if (!reduced) t.value = withTiming(1, { duration: motion.stamp, easing: Easing.out(Easing.back(2)) });
  }, [reduced, t]);
  const style = useAnimatedStyle(() => ({ opacity: Math.min(1, t.value * 2), transform: [{ scale: 1.5 - 0.5 * t.value }] }));
  return (
    <Animated.Text accessibilityRole="alert" style={[{
      color: result === 'success' ? colors.gold.fg : colors.danger.fg,
      fontSize: 26, lineHeight: 30, fontFamily: fontFamily.serif[0], letterSpacing: 2,
    }, style]}>
      {ko.result[result]}
    </Animated.Text>
  );
}

function Mods({ mods, shown, decisive = [] }: { mods: Chip[]; shown?: number; decisive?: number[] }) {
  return (
    <View className="flex-row flex-wrap justify-center" style={{ columnGap: 12, rowGap: 2 }}>
      {mods.map((m, i) => {
        const key = decisive.includes(i);
        return (
          <Text key={`${m.label}${i}`} className={`text-panel ${key ? 'font-sans-semibold' : 'font-sans'}`}
            style={{ color: colors.chip[m.kind], opacity: shown !== undefined && i >= shown ? 0.35 : 1 }}>
            {m.label} {m.kind === 'guard' ? `· ${ko.guarded}` : signed(m.value)}{key ? ` ${m.kind === 'hinder' ? ko.because : ko.thanks}` : ''}
          </Text>
        );
      })}
    </View>
  );
}

// `onResend` is given while the roll's answer is lost: the dice rest blank and the resend is the only control.
// The card covers the input bar, so a notice for a roll that came back with the card still open shows here.
export function RollCard({ card, onRoll, onCancel, onResend, notice, step, frame, rolling, explain = {} }: {
  card: Card; onRoll: (pick: string) => void; onCancel: () => void; onResend?: () => void; notice?: string | null;
  step?: StepRecord; frame?: Frame; rolling?: boolean;
  // What the ring means, said once a game: the first roll card, and the first one whose ring is red.
  explain?: { target?: boolean; high?: boolean };
}) {
  const first = card.options.find(plain) ?? card.options[card.options.length - 1];
  const [pick, setPick] = useState(card.selected ?? first.id);
  const chosen = card.options.find((o) => o.id === pick) ?? first;
  // Forcing is a toggle over the same reliances: each option has a twin in the other strain.
  const group = card.options.filter((o) => !!o.forced === !!chosen.forced);
  const none = group.find(plain) ?? first;
  const twin = card.options.find((o) => (o.rely ?? null) === (chosen.rely ?? null) && !!o.forced !== !!chosen.forced);
  const forcedGain = (chosen.forced ? chosen : twin)?.preview?.gain;
  const buys = forcedGain?.kind === 'fill' && (forcedGain.forced ?? 0) > 0;
  const p = chosen.preview as Preview;
  const target = card.plan.step?.target;
  const high = p.risk === 'high';
  const locked = rolling || !!step || !!onResend;
  const relyChip = (o: CardOption) => o.preview?.mods.find((m) => (m.kind === 'help' || m.kind === 'guard') && m.label === o.label);
  const fixed = p.mods.filter((m) => m.value !== 0 && m.kind !== 'help');
  const relyText = (c: Chip) => (c.kind === 'guard' ? ` · ${ko.guarded}` : ` ${signed(c.value)}`);
  const fill = target?.fill ?? 0;
  const own = step ? step.changes.findIndex((c) => c.kind === 'fill' && c.id === target?.id) : -1;
  const gained = frame && own >= 0 ? frame.boxes[own] ?? 0 : 0;
  const ref = useDialog(locked ? undefined : onCancel);

  const reduced = useReducedMotion();
  const open = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    if (!reduced) open.value = withTiming(1, { duration: motion.enter, easing: ease });
  }, [reduced, open]);
  // A failure jolts the card once as it lands.
  const jolt = useSharedValue(0);
  const settled = frame?.settled ?? null;
  useEffect(() => {
    if (settled !== 'fail' || reduced) return;
    const d = motion.jolt / 5;
    jolt.value = withSequence(withTiming(-6, { duration: d }), withTiming(6, { duration: d }), withTiming(-4, { duration: d }),
      withTiming(4, { duration: d }), withTiming(0, { duration: d }));
  }, [settled, reduced, jolt]);
  const enter = useAnimatedStyle(() => ({ opacity: open.value, transform: [{ translateX: jolt.value }, { scale: 0.96 + 0.04 * open.value }] }));

  return (
    <Animated.View style={enter}>
      <View ref={ref} accessibilityRole={'dialog' as never} aria-modal
        className="items-center gap-3 rounded-2xl border border-border-strong bg-canvas-floating px-5 pb-5 pt-3">
        <View className="min-h-[36px] w-full flex-row items-center">
          <View className="w-9" />
          <View className="min-w-0 flex-1 items-center gap-1">
            <Text className="text-center font-sans-semibold text-body text-fg-default">{card.plan.step?.label}</Text>
            {target?.boxes && target.boxes > 1 ? <Boxes fill={fill + gained} boxes={target.boxes} size={10} /> : null}
          </View>
          <View className="w-9">{!locked ? <IconButton icon="close" label={ko.close} onPress={onCancel} /> : null}</View>
        </View>
        <Target dc={p.dc} high={high} result={frame?.settled ?? null} />
        {!frame && (explain.target || (high && explain.high)) ? (
          <Text className="-mt-1 text-center font-sans text-chip" style={{ color: high && explain.high ? colors.danger.fg : colors.fg.muted }}>
            {[explain.target ? ko.atLeast(p.dc) : null, high && explain.high ? ko.irreversible : null].filter(Boolean).join(' · ')}
          </Text>
        ) : null}
        <Dice state={frame?.blocked ? 'gone' : step || rolling ? 'rolling' : onResend ? 'stopped' : 'ready'}
          values={frame ? frame.dice : [null, null]} label={ko.hold} cue={ko.roll} onRelease={() => onRoll(pick)} />
        <View className="h-[30px] items-center justify-center">
          {/* The total stays when the verdict lands beside it, so nobody has to add the dice up. */}
          <View className="flex-row items-center gap-3">
            {frame?.point != null ? <Text className="font-mono-medium text-title text-fg-default">{frame.point}</Text> : null}
            {frame?.settled ? <Verdict result={frame.settled} /> : null}
          </View>
        </View>
        {step && frame ? (
          <Mods mods={step.mods} decisive={frame.decisive} shown={frame.chips} />
        ) : (
          <View className="w-full items-center gap-1">
            {fixed.length ? <Mods mods={fixed} /> : null}
            {/* One help at most, so the rows are radio buttons; they share the widest row's width to line up. */}
            <View>
              {group.filter((o) => !plain(o)).map((o) => {
                const chip = relyChip(o);
                const on = o.id === pick;
                return (
                  <Pressable key={o.id} accessibilityRole="radio" accessibilityState={{ checked: on, disabled: locked }}
                    accessibilityLabel={`${o.label}${chip ? relyText(chip) : ''}${o.note ? ` · ${o.note}` : ''}`}
                    disabled={locked} onPress={() => setPick(on ? none.id : o.id)} style={pressed}
                    className="min-h-[32px] flex-row items-center gap-2 px-2">
                    <View className="h-4 w-4 items-center justify-center rounded-full border"
                      style={{ borderColor: on ? colors.chip.help : colors.border.strong }}>
                      {on ? <View className="h-2 w-2 rounded-full" style={{ backgroundColor: colors.chip.help }} /> : null}
                    </View>
                    <Text className={`font-sans text-panel ${on ? 'text-fg-default' : 'text-fg-muted'}`}>
                      {o.label}{chip ? <Text style={{ color: colors.chip[chip.kind] }}>{relyText(chip)}</Text> : null}
                      {o.note ? <Text className="text-fg-subtle"> · {o.note}</Text> : null}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
            {twin ? (
              <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: !!chosen.forced, disabled: locked }}
                accessibilityLabel={buys ? `${ko.forced} · ${ko.forcedGain}` : ko.forced} disabled={locked} onPress={() => setPick(twin.id)}
                style={pressed} className="min-h-[32px] flex-row items-center gap-2 px-2">
                <View className="h-4 w-4 items-center justify-center rounded-sm border"
                  style={{ borderColor: chosen.forced ? colors.danger.fg : colors.border.strong }}>
                  {chosen.forced ? <View className="h-2 w-2" style={{ backgroundColor: colors.danger.fg }} /> : null}
                </View>
                <Text className={`font-sans text-panel ${chosen.forced ? 'text-fg-default' : 'text-fg-muted'}`}>
                  {ko.forced}{buys ? <Text className="text-fg-subtle"> · {ko.forcedGain}</Text> : null}
                </Text>
              </Pressable>
            ) : null}
          </View>
        )}
        {notice ? <Notice text={notice} /> : null}
        {onResend ? <Resend onResend={onResend} /> : null}
        {frame?.blocked?.length ? (
          <Text className="font-sans-semibold text-title text-danger-fg">{frame.blocked.join(', ')}</Text>
        ) : null}
      </View>
    </Animated.View>
  );
}
