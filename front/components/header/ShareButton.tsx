import React from 'react';
import { Pressable } from 'react-native';
import Svg, { Path, Circle } from 'react-native-svg';
import { Theme } from '@/constants/theme';

export function ShareButton() {
  const [copied, setCopied] = React.useState(false);
  const onPress = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  return (
    <Pressable onPress={onPress} style={{
      width: 30, height: 30, borderRadius: Theme.radius.sm,
      backgroundColor: copied ? Theme.accentSoft : 'transparent',
      alignItems: 'center', justifyContent: 'center', flexShrink: 0,
    }}>
      {copied ? (
        <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={Theme.accent} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <Path d="M5 12l5 5L20 7" />
        </Svg>
      ) : (
        <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={Theme.textDim} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Circle cx={18} cy={5} r={2.6} />
          <Circle cx={6} cy={12} r={2.6} />
          <Circle cx={18} cy={19} r={2.6} />
          <Path d="M8.3 10.8l7.4-4.3M8.3 13.2l7.4 4.3" />
        </Svg>
      )}
    </Pressable>
  );
}
