import React from 'react';
import { View, Text, FlatList, Animated, Easing, Keyboard } from 'react-native';
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
  return <View style={{ height: spacing[5] }} />;
}

export function Log({
  log,
  rolling,
}: {
  log: LogEntry[];
  rolling: boolean;
}) {
  const ref = React.useRef<FlatList<LogEntry>>(null);
  const [viewportH, setViewportH] = React.useState(0);
  const initialized = React.useRef(false);

  const onContentSizeChange = React.useCallback((_w: number, h: number) => {
    const offset = Math.max(0, h - viewportH);
    ref.current?.scrollToOffset({ offset, animated: initialized.current });
    initialized.current = true;
  }, [viewportH]);

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
      ItemSeparatorComponent={Separator}
      ListFooterComponent={rolling ? <RollingIndicator /> : null}
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
