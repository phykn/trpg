import React from 'react';
import { Text, View, Pressable } from 'react-native';
import { Row } from './Row';
import { useExpandGroup } from './ExpandGroup';

export function LabeledRow({ label, children, mono = false }: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
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

  return (
    <Pressable onPress={canToggle ? toggle : undefined}>
      <Row label={label} variableHeight={expanded}>
        <View className="flex-row items-end gap-1">
          <View className="flex-1 min-w-0">
            <Text
              className={`${fontClass} text-panel text-fg-default`}
              numberOfLines={expanded ? undefined : 1}
              ellipsizeMode="clip"
            >
              {text}
            </Text>
            {!overflow && !expanded && (
              <Text
                className={`${fontClass} text-panel text-fg-default absolute inset-x-0 opacity-0`}
                onTextLayout={(e) => {
                  if (e.nativeEvent.lines.length > 1) setOverflow(true);
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
