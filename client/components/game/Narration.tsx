import { type ReactNode, useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useSharedValue, withDelay, withRepeat, withSequence, withTiming } from 'react-native-reanimated';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

import { Button } from '@/components/ui/Button';
import { useEnter } from '@/components/ui/motion';
import { colors, motion } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Narration as N } from '@/logic/useGame';
import type { Entry } from '@/logic/useLog';
import { Face } from './Dice';

const STORY = { fontSize: 16, lineHeight: 26 };

export type Roll = { d1: number; d2: number; total: number; result: string; dc?: number; approach?: string };

function Dot({ delay }: { delay: number }) {
  const t = useSharedValue(0);
  useEffect(() => {
    const ease = Easing.inOut(Easing.sin);
    t.value = withDelay(delay, withRepeat(withSequence(withTiming(1, { duration: 520, easing: ease }),
      withTiming(0, { duration: 520, easing: ease })), -1));
  }, [delay, t]);
  const style = useAnimatedStyle(() => ({ opacity: 0.25 + 0.75 * t.value, transform: [{ scale: 0.75 + 0.25 * t.value }] }));
  // Animated views take no className, so the dot is styled directly.
  return <Animated.View style={[{ width: 7, height: 7, borderRadius: 3.5, backgroundColor: colors.gold.fg }, style]} />;
}

// The only waiting signal: no words, just a chat partner typing.
export function Typing() {
  return (
    <View accessibilityLabel={ko.typing} className="h-[26px] flex-row items-center gap-[5px]">
      {[0, 180, 360].map((d) => <Dot key={d} delay={d} />)}
    </View>
  );
}

export function RollLine({ roll }: { roll: Roll }) {
  const won = roll.result === 'success';
  return (
    <View className="flex-row items-center gap-2">
      <View className="flex-row gap-1"><Face value={roll.d1} size={16} /><Face value={roll.d2} size={16} /></View>
      {roll.approach ? <Text className="font-sans text-panel text-fg-muted">{roll.approach}</Text> : null}
      <Text className={`font-sans-semibold text-panel ${won ? 'text-gold-fg' : 'text-danger-fg'}`}>{ko.result[roll.result]}</Text>
      <Text className="font-mono-medium text-chip text-fg-subtle">{roll.total}</Text>
      {/* The target sits in a small ring like the card's, so "9 ⑧" reads as total against target, not a fraction. */}
      {roll.dc ? (
        <View className="h-[18px] min-w-[18px] items-center justify-center rounded-full border border-border-strong px-1">
          <Text className="font-mono-medium text-fg-subtle" style={{ fontSize: 10, lineHeight: 12 }}>{roll.dc}</Text>
        </View>
      ) : null}
    </View>
  );
}

function Rise({ children, self }: { children: ReactNode; self?: 'end' }) {
  const enter = useEnter(8);
  return <Animated.View style={[enter, self === 'end' ? { alignSelf: 'flex-end', maxWidth: '85%' } : null]}>{children}</Animated.View>;
}

function Line({ entry }: { entry: Entry }) {
  if (entry.kind === 'you') {
    return (
      <Rise self="end">
        <View className="rounded-2xl rounded-br-md bg-gold-muted px-3.5 py-2">
          <Text className="font-sans text-panel text-fg-default">{entry.text}</Text>
        </View>
      </Rise>
    );
  }
  if (entry.kind === 'roll') return <Rise><RollLine roll={entry} /></Rise>;
  return <Rise><Text className="font-sans text-fg-default" style={STORY}>{entry.text}</Text></Rise>;
}

// Older lines fade into the rows above instead of being cut by a hard edge.
function TopFade() {
  return (
    <View pointerEvents="none" style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 20 }}>
      <Svg width="100%" height="100%">
        <Defs>
          <LinearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={colors.canvas.default} stopOpacity={1} />
            <Stop offset="1" stopColor={colors.canvas.default} stopOpacity={0} />
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill="url(#fade)" />
      </Svg>
    </View>
  );
}

export function Chat({ entries, live, roll, waiting, narration, hold, failed, onTyped, onRetry }: {
  entries: Entry[]; live: boolean; roll: Roll | null; waiting: boolean;
  narration: N; hold: boolean; failed: boolean; onTyped: () => void; onRetry: () => void;
}) {
  const scroll = useRef<ScrollView>(null);
  const [shown, setShown] = useState(0);
  const full = live ? [narration.text, narration.recap].filter(Boolean).join('\n\n') : '';
  const typedFor = useRef<string | null>(null);

  useEffect(() => {
    if (hold || !full) return undefined;
    setShown(0);
    const id = setInterval(() => setShown((n) => {
      if (n + 1 >= full.length) { clearInterval(id); return full.length; }
      return n + 1;
    }), 1000 / motion.typeRate);
    return () => clearInterval(id);
  }, [full, hold]);

  useEffect(() => {
    if (!hold && full && shown >= full.length && typedFor.current !== full) {
      typedFor.current = full;
      onTyped();
    }
  }, [shown, full, hold, onTyped]);

  const end = (animated: boolean) => scroll.current?.scrollToEnd({ animated });
  const typing = live && !hold && full && shown < full.length;
  return (
    <View className="min-h-0 flex-1">
      <ScrollView ref={scroll} showsVerticalScrollIndicator={false} className="min-h-0 flex-1"
        contentContainerStyle={{ gap: 14, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 }}
        onLayout={() => end(false)} onContentSizeChange={() => end(true)}>
        {entries.map((e) => <Line key={e.id} entry={e} />)}
        {live && roll && !hold ? <Rise><RollLine roll={roll} /></Rise> : null}
        {live && full && !hold ? (
          <Pressable accessibilityRole="text" accessibilityHint={ko.skip} onPress={() => setShown(full.length)}>
            <Text className="font-sans text-fg-default" style={STORY}>{full.slice(0, shown)}</Text>
          </Pressable>
        ) : null}
        {waiting && !failed && !typing && (hold || !full) ? <Typing /> : null}
        {failed ? (
          <View accessibilityRole="alert" className="items-start gap-2">
            <Text className="font-sans-semibold text-body text-danger-fg">{ko.narrationFailed}</Text>
            {narration.error ? <Text className="font-sans text-chip text-fg-subtle">{narration.error}</Text> : null}
            <Button icon="retry" label={ko.retryNarration} onPress={onRetry} />
          </View>
        ) : null}
      </ScrollView>
      <TopFade />
    </View>
  );
}
