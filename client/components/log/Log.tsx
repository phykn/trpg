import React from 'react';
import { View, FlatList, Animated, Easing, Keyboard } from 'react-native';
import { colors, spacing } from '@/design/tokens';

import { LogItem } from './LogItem';
import type { LogEntry } from '@/logic/log/types';

function TypingDot({ delay }: { delay: number }) {
  const anim = React.useRef(new Animated.Value(0)).current;
  React.useEffect(() => {
    const cycle = Animated.sequence([
      Animated.timing(anim, {
        toValue: -4,
        duration: 320,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.timing(anim, {
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
  }, [anim, delay]);
  return (
    <Animated.View
      style={{
        width: 6,
        height: 6,
        borderRadius: 3,
        backgroundColor: colors.fg.muted,
        transform: [{ translateY: anim }],
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

export function Log({
  log,
  typing,
}: {
  log: LogEntry[];
  typing: boolean;
}) {
  const ref = React.useRef<FlatList<LogEntry>>(null);
  const [viewportH, setViewportH] = React.useState(0);
  const contentH = React.useRef(0);
  const initialized = React.useRef(false);

  const syncScrollPosition = React.useCallback((h = contentH.current, v = viewportH) => {
    if (v <= 0) return;
    if (h <= v) {
      ref.current?.scrollToOffset({ offset: 0, animated: false });
      initialized.current = true;
      return;
    }
    const offset = h - v;
    ref.current?.scrollToOffset({ offset, animated: initialized.current });
    initialized.current = true;
  }, [viewportH]);

  const onContentSizeChange = (_w: number, h: number) => {
    contentH.current = h;
    syncScrollPosition(h);
  };

  React.useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', () => {
      ref.current?.scrollToEnd({ animated: true });
    });
    return () => show.remove();
  }, []);

  return (
    <FlatList
      ref={ref}
      style={{ flex: 1 }}
      data={log}
      keyExtractor={(e) => String(e.id)}
      renderItem={({ item }) => <LogItem entry={item} />}
      ListFooterComponent={typing ? <TypingDots /> : null}
      ItemSeparatorComponent={() => <View style={{ height: spacing[4] }} />}
      onLayout={(ev) => {
        const nextViewportH = ev.nativeEvent.layout.height;
        setViewportH(nextViewportH);
        syncScrollPosition(contentH.current, nextViewportH);
      }}
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
