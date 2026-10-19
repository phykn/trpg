import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useSharedValue, withDelay, withRepeat, withSequence, withTiming } from 'react-native-reanimated';

import { colors, motion } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Narration as N } from '@/logic/useGame';
import type { Entry } from '@/logic/useLog';

const FACE = ['', '⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];
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
  return (
    <Text className="font-sans text-panel text-fg-muted">
      <Text className="font-mono-medium">{FACE[roll.d1]}{FACE[roll.d2]}</Text>
      {roll.approach ? ` ${ko.check(roll.approach)} ` : ' '}
      <Text className={`font-sans-semibold ${roll.result === 'success' ? 'text-gold-fg' : 'text-danger-fg'}`}>
        {ko.result[roll.result as keyof typeof ko.result]}
      </Text>
      <Text className="font-mono-medium text-fg-subtle"> {roll.total}{roll.dc ? `/${roll.dc}` : ''}</Text>
    </Text>
  );
}

function Line({ entry }: { entry: Entry }) {
  if (entry.kind === 'you') {
    return (
      <View className="max-w-[85%] self-end rounded-lg bg-accent-muted px-3 py-1.5">
        <Text className="font-sans text-panel text-fg-default">{entry.text}</Text>
      </View>
    );
  }
  if (entry.kind === 'roll') return <RollLine roll={entry} />;
  return <Text className="font-sans text-fg-default" style={STORY}>{entry.text}</Text>;
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
    <ScrollView ref={scroll} showsVerticalScrollIndicator={false} className="min-h-0 flex-1" contentContainerStyle={{ gap: 12, paddingHorizontal: 16, paddingVertical: 12 }}
      onLayout={() => end(false)} onContentSizeChange={() => end(true)}>
      {entries.map((e) => <Line key={e.id} entry={e} />)}
      {live && roll && !hold ? <RollLine roll={roll} /> : null}
      {live && full && !hold ? (
        <Pressable accessibilityRole="text" onPress={() => setShown(full.length)}>
          <Text className="font-sans text-fg-default" style={STORY}>{full.slice(0, shown)}</Text>
        </Pressable>
      ) : null}
      {waiting && !failed && !typing && (hold || !full) ? <Typing /> : null}
      {failed ? (
        <View className="gap-2">
          <Text accessibilityRole="alert" className="font-sans-semibold text-body text-danger-fg">{ko.narrationFailed}</Text>
          {narration.error ? <Text className="font-sans text-chip text-fg-subtle">{narration.error}</Text> : null}
          <Pressable accessibilityRole="button" onPress={onRetry} className="self-start rounded-md border border-border-default px-3 py-1">
            <Text className="font-sans text-panel text-fg-default">{ko.retryNarration}</Text>
          </Pressable>
        </View>
      ) : null}
    </ScrollView>
  );
}
