import React from 'react';
import { View, Text, ScrollView, Animated, Easing } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';
import type { LogEntry } from '@/types/game';
import { LogItem } from './LogItem';

function Pulse({ color }: { color: string }) {
  const anim = React.useRef(new Animated.Value(1)).current;
  React.useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 0.4, duration: 500, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(anim, { toValue: 1,   duration: 500, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [anim]);
  return (
    <Animated.View style={{
      width: 6, height: 6, borderRadius: 3, backgroundColor: color,
      opacity: anim,
      transform: [{ scale: anim.interpolate({ inputRange: [0.4, 1], outputRange: [0.85, 1] }) }],
    }} />
  );
}

export function Log({ log, rolling }: { log: LogEntry[]; rolling: boolean }) {
  const ref = React.useRef<ScrollView>(null);
  React.useEffect(() => {
    ref.current?.scrollToEnd({ animated: true });
  }, [log.length, rolling]);

  return (
    <ScrollView
      ref={ref}
      style={{ flex: 1 }}
      contentContainerStyle={{
        paddingHorizontal: Theme.space.xl,
        paddingTop: Theme.space.lg,
        paddingBottom: Theme.space.sm,
        gap: Theme.space.lg + 2,
      }}
      showsVerticalScrollIndicator={false}
    >
      {log.map(e => <LogItem key={e.id} entry={e} />)}
      {rolling && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: Theme.space.sm + 2 }}>
          <Pulse color={Theme.accent} />
          <Text style={{ color: Theme.accent, fontFamily: Theme.fonts.sansRegular, ...typeStyle('body') }}>
            주사위를 굴리는 중…
          </Text>
        </View>
      )}
    </ScrollView>
  );
}
