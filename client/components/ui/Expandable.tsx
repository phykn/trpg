import React from 'react';
import { Pressable, StyleProp, Text, TextStyle, View } from 'react-native';

// Shared "tap to expand a clamped text" primitive. The visible Text gets
// `numberOfLines={clampLines}` while collapsed; an invisible duplicate of
// the same text (`measureText`) is rendered absolutely so its onLayout
// height tells us whether the content overflows. `contentKey` triggers
// the reset — when it changes (caller decides what counts: the raw text,
// or text + tone for rich segments) we forget the prior overflow/expanded
// state and re-measure.
//
// `children` is what the user sees; for inline-styled segments pass them
// as nested `<Text>` elements so RN renders them on the same line. The
// measurement Text uses `measureText` (a plain string) so the inline
// styling doesn't interfere with height measurement.
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
