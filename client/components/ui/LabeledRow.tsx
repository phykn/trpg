import React from 'react';
import { Text, Pressable } from 'react-native';
import { Row } from './Row';
import { useExpandGroup } from './ExpandGroup';

export function LabeledRow({ id, label, children, mono = false, clampLines = 3 }: {
  id?: string;
  label: string;
  children: React.ReactNode;
  mono?: boolean;
  clampLines?: number;
}) {
  const isText = typeof children === 'string' || typeof children === 'number';
  const { expanded, toggle } = useExpandGroup(id ?? label);
  const text = isText ? String(children) : '';

  if (!isText) {
    return <Row label={label} variableHeight>{children}</Row>;
  }

  const fontClass = mono ? 'font-mono' : 'font-sans';
  const canToggle = expanded || canExpandText(text, clampLines);
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
      </Row>
    </Pressable>
  );
}

function canExpandText(text: string, clampLines: number): boolean {
  const explicitLines = text.split('\n').length;
  if (explicitLines > clampLines) return true;
  return text.length > clampLines * 28;
}
