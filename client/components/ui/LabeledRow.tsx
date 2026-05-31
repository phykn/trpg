import React from 'react';
import { Text, Pressable, View } from 'react-native';
import { Row } from './Row';
import { useExpandGroup } from './ExpandGroup';
import { ko } from '@/locale/ko';

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
  const lines = text.split('\n');
  const canUseTitleBodyLayout = !mono && lines.length > 1;
  const titleLine = canUseTitleBodyLayout ? lines[0] : null;
  const bodyText = canUseTitleBodyLayout ? lines.slice(1).join('\n') : text;
  const bodyClampLines = titleLine ? Math.max(1, clampLines - 1) : clampLines;

  return (
    <Pressable onPress={canToggle ? toggle : undefined}>
      <Row
        label={label}
        variableHeight={multiLine}
        trailing={canToggle ? (
          <Text
            className="font-sans text-caption text-fg-subtle"
            accessibilityLabel={expanded ? ko.panel.collapse : ko.panel.expand}
          >
            {expanded ? '⌃' : '⌄'}
          </Text>
        ) : undefined}
      >
        {titleLine ? (
          <View className="gap-0.5">
            <Text
              className="font-sans-semibold text-panel text-fg-default"
              numberOfLines={expanded ? undefined : 1}
              ellipsizeMode="tail"
            >
              {titleLine}
            </Text>
            <Text
              className="font-sans text-caption text-fg-muted"
              numberOfLines={expanded ? undefined : bodyClampLines}
              ellipsizeMode="tail"
            >
              {bodyText}
            </Text>
          </View>
        ) : (
          <Text
            className={`${fontClass} text-panel text-fg-default`}
            numberOfLines={expanded ? undefined : clampLines}
            ellipsizeMode="tail"
          >
            {text}
          </Text>
        )}
      </Row>
    </Pressable>
  );
}

function canExpandText(text: string, clampLines: number): boolean {
  const explicitLines = text.split('\n').length;
  if (explicitLines > clampLines) return true;
  return text.length > clampLines * 28;
}
