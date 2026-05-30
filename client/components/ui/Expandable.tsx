import React from 'react';
import { Pressable, StyleProp, Text, TextStyle, View } from 'react-native';

// Tap-to-expand a clamped text. An absolutely-positioned duplicate measures overflow; `contentKey` triggers a reset.
export function Expandable({
  contentKey,
  lineHeight,
  clampLines = 1,
  textClassName,
  textStyle,
  measureText,
  children,
  pressableClassName,
}: {
  contentKey: string;
  lineHeight: number;
  clampLines?: number;
  textClassName: string;
  textStyle?: StyleProp<TextStyle>;
  measureText: string;
  children: React.ReactNode;
  pressableClassName?: string;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const [overflow, setOverflow] = React.useState(false);
  React.useEffect(() => {
    setOverflow(false);
    setExpanded(false);
  }, [contentKey]);
  const canToggle = overflow || expanded;

  return (
    <Pressable
      onPress={canToggle ? () => setExpanded((v) => !v) : undefined}
      className={pressableClassName}
    >
      <View>
        <Text
          numberOfLines={expanded ? undefined : clampLines}
          className={textClassName}
          style={textStyle}
        >
          {children}
        </Text>
        {!overflow && !expanded && (
          <View
            className="absolute inset-x-0 opacity-0"
            style={{ pointerEvents: 'none' }}
            aria-hidden
            accessibilityElementsHidden
            importantForAccessibility="no-hide-descendants"
            onLayout={(e) => {
              if (e.nativeEvent.layout.height > lineHeight * clampLines + 1) {
                setOverflow(true);
              }
            }}
          >
            <Text className={textClassName} style={textStyle}>
              {measureText}
            </Text>
          </View>
        )}
      </View>
    </Pressable>
  );
}
