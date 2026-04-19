import React from 'react';
import { View, Text, Pressable, Animated } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Theme, typeStyle } from '@/constants/theme';
import { HeroDetail } from './HeroDetail';
import type { Hero } from '@/types/game';

function Stat({ label, value, valueColor = Theme.text }: {
  label: string; value: string | number; valueColor?: string;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 4 }}>
      <Text style={{ ...typeStyle('caption'), color: Theme.textFaint, fontFamily: Theme.fonts.monoRegular }}>{label}</Text>
      <Text style={{ ...typeStyle('caption'), color: valueColor, fontFamily: Theme.fonts.monoRegular, fontVariant: ['tabular-nums'] }}>{value}</Text>
    </View>
  );
}

export function HeroPill({ hero, expanded, onToggle }: {
  hero: Hero; expanded: boolean; onToggle: () => void;
}) {
  const rot = React.useRef(new Animated.Value(expanded ? 1 : 0)).current;
  React.useEffect(() => {
    Animated.timing(rot, { toValue: expanded ? 1 : 0, duration: 180, useNativeDriver: true }).start();
  }, [expanded, rot]);
  const rotate = rot.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] });

  return (
    <View style={{ marginHorizontal: Theme.space.lg }}>
      <Pressable onPress={onToggle} style={{
        height: 34, backgroundColor: Theme.bgCard,
        borderWidth: 1, borderColor: Theme.border,
        borderRadius: Theme.radius.pill, paddingHorizontal: Theme.space.md,
        flexDirection: 'row', alignItems: 'center', gap: Theme.space.md,
      }}>
        <Text numberOfLines={1} style={{
          ...typeStyle('caption', { fontWeight: '600' as const }),
          color: Theme.text, flexShrink: 0, maxWidth: '32%',
          fontFamily: Theme.fonts.sansSemibold,
        }}>{hero.name}</Text>

        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'baseline', gap: Theme.space.sm }}>
          <Stat label="Lv" value={hero.level} />
          <Stat label="HP" value={`${hero.hp}/${hero.hpMax}`} valueColor={Theme.hp} />
          {hero.mp != null && (
            <Stat label="MP" value={`${hero.mp}/${hero.mpMax}`} valueColor={Theme.mp} />
          )}
        </View>

        {hero.status?.length > 0 && (
          <View style={{
            flexDirection: 'row', alignItems: 'center', gap: 6,
            paddingLeft: Theme.space.sm,
            borderLeftWidth: 1, borderLeftColor: Theme.border,
          }}>
            <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: Theme.good }} />
            <Text style={{
              ...typeStyle('caption', { fontWeight: '500' as const }),
              color: Theme.textDim, fontFamily: Theme.fonts.sansMedium,
            }}>{hero.status.join(' · ')}</Text>
          </View>
        )}

        <Animated.View style={{ transform: [{ rotate }] }}>
          <Svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke={Theme.textFaint} strokeWidth={2.2}>
            <Path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
          </Svg>
        </Animated.View>
      </Pressable>

      {expanded && <HeroDetail hero={hero} />}
    </View>
  );
}
