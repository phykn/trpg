import React from 'react';
import { View, Text, Pressable, FlatList, Animated, Easing, Keyboard } from 'react-native';
import { colors, spacing } from '@/design/tokens';
import type { LogEntry } from '@/types/ui';
import { LogItem } from './LogItem';

function Pulse({ color }: { color: string }) {
  const anim = React.useRef(new Animated.Value(1)).current;
  React.useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 0.4, duration: 500, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(anim, { toValue: 1,   duration: 500, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [anim]);
  return (
    <Animated.View
      style={{
        width: 6, height: 6, borderRadius: 3, backgroundColor: color,
        opacity: anim,
        transform: [{ scale: anim.interpolate({ inputRange: [0.4, 1], outputRange: [0.85, 1] }) }],
      }}
    />
  );
}

function RollingIndicator() {
  return (
    <View className="flex-row items-center gap-2.5" style={{ paddingTop: spacing[5] }}>
      <Pulse color={colors.accent.fg} />
      <Text className="font-sans text-body text-accent-fg">
        주사위를 굴리는 중…
      </Text>
    </View>
  );
}

function Separator() {
  return (
    <View
      style={{ height: spacing[5], alignItems: 'center', justifyContent: 'center' }}
    >
      <Text style={{ color: colors.fg.subtle, fontSize: 9, letterSpacing: 5 }}>
        · · ·
      </Text>
    </View>
  );
}

function TypingDot({ delay }: { delay: number }) {
  const v = React.useRef(new Animated.Value(0)).current;
  React.useEffect(() => {
    const cycle = Animated.sequence([
      Animated.timing(v, {
        toValue: -4,
        duration: 320,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.timing(v, {
        toValue: 0,
        duration: 320,
        easing: Easing.in(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.delay(240),
    ]);
    const loop = Animated.loop(cycle);
    const start = setTimeout(() => loop.start(), delay);
    return () => {
      clearTimeout(start);
      loop.stop();
    };
  }, [v, delay]);
  return (
    <Animated.View
      style={{
        width: 6,
        height: 6,
        borderRadius: 3,
        backgroundColor: colors.fg.muted,
        transform: [{ translateY: v }],
      }}
    />
  );
}

function TypingDots() {
  return (
    <View
      style={{
        borderLeftWidth: 2,
        borderLeftColor: colors.accent.fg,
        paddingLeft: spacing[3],
        paddingVertical: spacing[2],
      }}
    >
      <View
        className="flex-row items-center"
        style={{ gap: spacing[1.5], height: 12 }}
      >
        <TypingDot delay={0} />
        <TypingDot delay={120} />
        <TypingDot delay={240} />
      </View>
    </View>
  );
}

function SuggestionChips({
  items,
  onPick,
}: {
  items: string[];
  onPick: (text: string) => void;
}) {
  return (
    <View style={{ paddingTop: spacing[3], gap: spacing[1.5] }}>
      {items.map((text, i) => (
        <Pressable
          key={`${i}-${text}`}
          onPress={() => onPick(text)}
          className="px-3 py-1.5 rounded-full bg-accent-muted border border-border-default active:opacity-60"
        >
          <Text className="font-sans text-title text-fg-default text-center">
            {text}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

export function Log({
  log,
  rolling,
  typing,
  suggestions,
  onPickSuggestion,
}: {
  log: LogEntry[];
  rolling: boolean;
  typing: boolean;
  suggestions: string[];
  onPickSuggestion: (text: string) => void;
}) {
  const ref = React.useRef<FlatList<LogEntry>>(null);
  const [viewportH, setViewportH] = React.useState(0);
  const initialized = React.useRef(false);

  const onContentSizeChange = (_w: number, h: number) => {
    const offset = Math.max(0, h - viewportH);
    ref.current?.scrollToOffset({ offset, animated: initialized.current });
    initialized.current = true;
  };

  React.useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', () => {
      ref.current?.scrollToEnd({ animated: true });
    });
    return () => show.remove();
  }, []);

  React.useEffect(() => {
    if (initialized.current && viewportH > 0) {
      ref.current?.scrollToEnd({ animated: false });
    }
  }, [viewportH]);

  return (
    <FlatList
      ref={ref}
      style={{ flex: 1 }}
      data={log}
      keyExtractor={(e) => String(e.id)}
      renderItem={({ item }) => <LogItem entry={item} />}
      ItemSeparatorComponent={Separator}
      ListFooterComponent={
        rolling
          ? <RollingIndicator />
          : typing
          ? <TypingDots />
          : suggestions.length > 0
          ? <SuggestionChips items={suggestions} onPick={onPickSuggestion} />
          : null
      }
      onLayout={(ev) => setViewportH(ev.nativeEvent.layout.height)}
      onContentSizeChange={onContentSizeChange}
      contentContainerStyle={{
        paddingHorizontal: spacing[5],
        paddingTop: spacing[5],
        paddingBottom: spacing[6],
      }}
      showsVerticalScrollIndicator={false}
    />
  );
}
