import React from 'react';
import { View, Text, ScrollView, Animated, Easing, Keyboard } from 'react-native';
import { colors } from '@/design/tokens';
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

export function Log({ log, rolling }: { log: LogEntry[]; rolling: boolean }) {
  const ref = React.useRef<ScrollView>(null);
  const itemYs = React.useRef<Map<number, number>>(new Map());
  const prevLog = React.useRef<LogEntry[]>(log);
  const pendingTopId = React.useRef<number | null>(null);

  // New player message pins to viewport top; otherwise follow bottom. Actual
  // scroll happens after layout via onLayout / onContentSizeChange.
  React.useEffect(() => {
    const prev = prevLog.current;
    prevLog.current = log;
    const added = log.slice(prev.length);
    const newPlayer = [...added].reverse().find((e) => e.kind === 'player');
    if (!newPlayer) return;

    const y = itemYs.current.get(newPlayer.id);
    if (y !== undefined) {
      ref.current?.scrollTo({ y, animated: true });
    } else {
      pendingTopId.current = newPlayer.id;
    }
  }, [log]);

  const onItemLayout = React.useCallback((id: number, y: number) => {
    itemYs.current.set(id, y);
    if (pendingTopId.current === id) {
      ref.current?.scrollTo({ y, animated: true });
      pendingTopId.current = null;
    }
  }, []);

  const onContentSizeChange = React.useCallback(() => {
    if (pendingTopId.current !== null) return;
    ref.current?.scrollToEnd({ animated: true });
  }, []);

  React.useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', () => {
      if (pendingTopId.current !== null) return;
      ref.current?.scrollToEnd({ animated: true });
    });
    return () => show.remove();
  }, []);

  return (
    <ScrollView
      ref={ref}
      onContentSizeChange={onContentSizeChange}
      className="flex-1"
      contentContainerClassName="px-5 pt-5 pb-2 gap-5"
      showsVerticalScrollIndicator={false}
    >
      {log.map((e) => (
        <View
          key={e.id}
          onLayout={(ev) => onItemLayout(e.id, ev.nativeEvent.layout.y)}
        >
          <LogItem entry={e} />
        </View>
      ))}
      {rolling && (
        <View className="flex-row items-center gap-2.5">
          <Pulse color={colors.accent.fg} />
          <Text className="font-sans text-body text-accent-fg">
            주사위를 굴리는 중…
          </Text>
        </View>
      )}
    </ScrollView>
  );
}
