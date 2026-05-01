import React from 'react';
import { Text, View, Pressable } from 'react-native';
import { Row } from './Row';
import { useExpandGroup } from './ExpandGroup';

export function LabeledRow({ label, children, mono = false, clampLines = 1 }: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
  clampLines?: number;
}) {
  const isText = typeof children === 'string' || typeof children === 'number';
  const { expanded, toggle } = useExpandGroup(label);
  const [overflow, setOverflow] = React.useState(false);
  const text = isText ? String(children) : '';

  React.useEffect(() => {
    setOverflow(false);
  }, [text]);

  if (!isText) {
    return <Row label={label}>{children}</Row>;
  }

  const fontClass = mono ? 'font-mono' : 'font-sans';
  const canToggle = overflow || expanded;
  const showHint = overflow && !expanded;
  const multiLine = expanded || clampLines > 1;

  return (
    <Pressable onPress={canToggle ? toggle : undefined}>
      <Row label={label} variableHeight={multiLine}>
        <Text
          className={`${fontClass} text-panel text-fg-default`}
          numberOfLines={expanded ? undefined : clampLines}
          ellipsizeMode="clip"
        >
          {text}
        </Text>
        {!overflow && !expanded && (
          <View
            className="absolute inset-x-0 opacity-0"
            pointerEvents="none"
            onLayout={(e) => {
              // text-panel line-height is 18px (design/tokens.js).
              // onTextLayout doesn't fire on react-native-web, so detect
              // overflow by measuring the unclamped height instead.
              // 펼치기 힌트는 3줄 이상일 때만 노출.
              const minLines = Math.max(clampLines, 2);
              if (e.nativeEvent.layout.height > 18 * minLines + 1) setOverflow(true);
            }}
          >
            <Text className={`${fontClass} text-panel text-fg-default`}>
              {text}
            </Text>
          </View>
        )}
        {showHint && (
          <View
            className="absolute bottom-0 right-0 bg-canvas-subtle pl-3"
            pointerEvents="none"
          >
            <Text className={`${fontClass} text-panel text-fg-subtle`}>(펼치기)</Text>
          </View>
        )}
      </Row>
    </Pressable>
  );
}
