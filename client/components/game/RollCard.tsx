import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated, {
  Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming,
} from 'react-native-reanimated';

import { IconButton, pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { useDialog } from '@/components/ui/useDialog';
import { colors, fontFamily, motion } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Frame } from '@/logic/reveal';
import type { Card, CardOption, Chip, Preview, StepRecord } from '@/services/types';
import { Boxes } from './Boxes';
import { Notice, Resend } from './CommandBar';
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
      <View className="h-16 w-16 items-center justify-center rounded-full"
        style={{ borderWidth: result ? 2 : 1.5, borderColor: ring, backgroundColor: result === 'success' ? colors.gold.muted : 'transparent' }}>
        <Text className="font-mono-medium" style={{ fontSize: 28, lineHeight: 34, color: high && !result ? colors.danger.fg : colors.fg.default }}>{dc}</Text>
      </View>
      {high ? (
        <View accessibilityLabel={ko.highRisk} className="absolute -right-1 -top-1 h-6 w-6 items-center justify-center rounded-full bg-canvas-floating">
          <Icon name="alert" size={16} color={colors.danger.fg} width={2} />
        </View>
      ) : null}
    </View>
  );
}

function Verdict({ result }: { result: string }) {
  const reduced = useReducedMotion();
  const t = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    if (!reduced) t.value = withTiming(1, { duration: 400, easing: ease });
  }, [reduced, t]);
  const style = useAnimatedStyle(() => ({ opacity: t.value, transform: [{ translateY: (1 - t.value) * 6 }] }));
  return (
    <Animated.Text accessibilityRole="alert" style={[{
      color: result === 'success' ? colors.gold.fg : colors.danger.fg,
      fontSize: 22, lineHeight: 30, fontFamily: fontFamily['sans-semibold'][0], letterSpacing: 2,
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
            {m.label} {signed(m.value)}{key ? ` ${m.kind === 'hinder' ? ko.because : ko.thanks}` : ''}
          </Text>
        );
      })}
    </View>
  );
}

// `onResend` is given while the roll's answer is lost: the dice rest blank and the resend is the only control.
// The card covers the input bar, so a notice for a roll that came back with the card still open shows here.
export function RollCard({ card, onRoll, onCancel, onResend, notice, step, frame, rolling }: {
  card: Card; onRoll: (pick: string) => void; onCancel: () => void; onResend?: () => void; notice?: string | null;
  step?: StepRecord; frame?: Frame; rolling?: boolean;
}) {
  const none = card.options.find(plain) ?? card.options[card.options.length - 1];
  const [pick, setPick] = useState(card.selected ?? none.id);
  const chosen = card.options.find((o) => o.id === pick) ?? none;
  const p = chosen.preview as Preview;
  const target = card.plan.step?.target;
  const high = p.risk === 'high';
  const locked = rolling || !!step || !!onResend;
  const relyChip = (o: CardOption) => o.preview?.mods.find((m) => m.kind === 'help' && m.label === o.label);
  const fixed = p.mods.filter((m) => m.value !== 0 && m.kind !== 'help');
  const fill = target?.fill ?? 0;
  const own = step ? step.changes.findIndex((c) => c.kind === 'fill' && c.id === target?.id) : -1;
  const gained = frame && own >= 0 ? frame.boxes[own] ?? 0 : 0;
  const ref = useDialog(locked ? undefined : onCancel);

  const reduced = useReducedMotion();
  const open = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    if (!reduced) open.value = withTiming(1, { duration: motion.enter, easing: ease });
  }, [reduced, open]);
  const enter = useAnimatedStyle(() => ({ opacity: open.value, transform: [{ scale: 0.96 + 0.04 * open.value }] }));

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
        <Dice state={frame?.blocked ? 'gone' : step || rolling ? 'rolling' : onResend ? 'stopped' : 'ready'}
          values={frame ? frame.dice : [null, null]} label={ko.hold} onRelease={() => onRoll(pick)} />
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
              {card.options.filter((o) => !plain(o)).map((o) => {
                const chip = relyChip(o);
                const on = o.id === pick;
                return (
                  <Pressable key={o.id} accessibilityRole="radio" accessibilityState={{ checked: on, disabled: locked }}
                    accessibilityLabel={[o.label, chip ? signed(chip.value) : '', o.note ? `· ${o.note}` : ''].filter(Boolean).join(' ')}
                    disabled={locked} onPress={() => setPick(on ? none.id : o.id)} style={pressed}
                    className="min-h-[32px] flex-row items-center gap-2 px-2">
                    <View className="h-4 w-4 items-center justify-center rounded-full border"
                      style={{ borderColor: on ? colors.chip.help : colors.border.strong }}>
                      {on ? <View className="h-2 w-2 rounded-full" style={{ backgroundColor: colors.chip.help }} /> : null}
                    </View>
                    <Text className={`font-sans text-panel ${on ? 'text-fg-default' : 'text-fg-muted'}`}>
                      {o.label}{chip ? <Text style={{ color: colors.chip.help }}> {signed(chip.value)}</Text> : null}
                      {o.note ? <Text className="text-fg-subtle"> · {o.note}</Text> : null}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
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
