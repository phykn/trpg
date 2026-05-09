import React from 'react';
import { Text, View, Pressable } from 'react-native';
import { Row } from './Row';
import { useExpandGroup } from './ExpandGroup';

export function LabeledRow({ label, children, mono = false, clampLines = 3 }: {
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
  const multiLine = expanded || clampLines > 1;

  return (
    <Pressable onPress={canToggle ? toggle : undefined}>
      <Row label={label} variableHeight={multiLine}>
        <Text
          className={`${fontClass} text-panel text-fg-default`}
          numberOfLines={expanded ? undefined : clampLines}
          ellipsizeMode="tail"
        >
          {text}
        </Text>
        {!overflow && !expanded && (
          <View
            className="absolute inset-x-0 opacity-0"
            pointerEvents="none"
            onLayout={(e) => {
              // onTextLayout doesn't fire on react-native-web, so measure the unclamped height (line-height = 18px).
              if (e.nativeEvent.layout.height > 18 * clampLines + 1) setOverflow(true);
            }}
          >
            <Text className={`${fontClass} text-panel text-fg-default`}>
              {text}
            </Text>
          </View>
        )}
      </Row>
    </Pressable>
  );
}
