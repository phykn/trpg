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
        <View className="flex-row items-end gap-1">
          <View className="flex-1 min-w-0">
            <Text
              className={`${fontClass} text-panel text-fg-default`}
              numberOfLines={expanded ? undefined : clampLines}
              ellipsizeMode="clip"
            >
              {text}
            </Text>
            {!overflow && !expanded && (
              <Text
                className={`${fontClass} text-panel text-fg-default absolute inset-x-0 opacity-0`}
                onTextLayout={(e) => {
                  if (e.nativeEvent.lines.length > clampLines) setOverflow(true);
                }}
              >
                {text}
              </Text>
            )}
          </View>
          {showHint && (
            <Text className={`${fontClass} text-panel text-fg-subtle`}>(펼치기)</Text>
          )}
        </View>
      </Row>
    </Pressable>
  );
}
