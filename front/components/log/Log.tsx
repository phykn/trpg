import React from 'react';
import { View, Text, ScrollView, Animated, Easing, Keyboard } from 'react-native';
import { colors } from '@/design/tokens';
import type { LogEntry } from '@/types/domain';
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
  React.useEffect(() => {
    ref.current?.scrollToEnd({ animated: true });
  }, [log.length, rolling]);

  React.useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', () => {
      ref.current?.scrollToEnd({ animated: true });
    });
    return () => show.remove();
  }, []);

  return (
    <ScrollView
      ref={ref}
      className="flex-1"
      contentContainerClassName="px-5 pt-5 pb-2 gap-5"
      showsVerticalScrollIndicator={false}
    >
      {log.map((e) => <LogItem key={e.id} entry={e} />)}
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
