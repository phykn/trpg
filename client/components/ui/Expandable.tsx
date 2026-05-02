import React from 'react';
import { Pressable, StyleProp, Text, TextStyle, View } from 'react-native';

// Tap-to-expand a clamped text. An absolutely-positioned duplicate measures overflow; `contentKey` triggers a reset.
export function Expandable({
  contentKey,
  lineHeight,
  clampLines = 1,
  showHint = false,
  textClassName,
  textStyle,
  measureText,
  children,
  pressableClassName,
}: {
  contentKey: string;
  lineHeight: number;
  clampLines?: number;
  showHint?: boolean;
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
  const showHintNow = showHint && overflow && !expanded;

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
            pointerEvents="none"
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
        {showHintNow && (
          <View
            className="absolute bottom-0 right-0 bg-canvas-subtle pl-3"
            pointerEvents="none"
          >
            <Text className="font-sans text-caption text-fg-subtle">(펼치기)</Text>
          </View>
        )}
      </View>
    </Pressable>
  );
}
