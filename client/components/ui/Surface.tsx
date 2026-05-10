import React from 'react';
import { View, type ViewProps, type ViewStyle } from 'react-native';

import { shadow } from '@/design/tokens';

type SurfaceProps = {
  variant?: 'paper' | 'floating';
  stripeColor?: string;
  className?: string;
  style?: ViewStyle | ViewStyle[];
  children: React.ReactNode;
} & Omit<ViewProps, 'style' | 'children' | 'className'>;

const PAPER_CLASS = 'bg-canvas-subtle border border-border-default rounded-lg';
const FLOATING_CLASS = 'bg-canvas-floating border border-border-strong rounded-lg';

export function Surface({
  variant = 'paper',
  stripeColor,
  className,
  style,
  children,
  ...rest
}: SurfaceProps) {
  const shadowStyle = variant === 'floating' ? shadow.floating : shadow.paper;
  const stripeStyle: ViewStyle | null = stripeColor
    ? { borderLeftWidth: 2, borderLeftColor: stripeColor }
    : null;
  const base = variant === 'floating' ? FLOATING_CLASS : PAPER_CLASS;
  const composedClass = className ? `${base} ${className}` : base;
  const composedStyle = [shadowStyle, stripeStyle, style].filter(Boolean) as ViewStyle[];
  return (
    <View {...rest} className={composedClass} style={composedStyle}>
      {children}
    </View>
  );
}
