import { ScrollView, Text, View } from 'react-native';

import type { DecisionStateItem, DecisionStateTone } from '@/logic/decision-state/types';

function containerToneClass(tone: DecisionStateTone): string {
  if (tone === 'danger') return 'border-danger-fg bg-canvas-subtle';
  if (tone === 'warning') return 'border-accent-fg bg-canvas-subtle';
  if (tone === 'accent') return 'border-accent-fg bg-accent-muted';
  return 'border-border-default bg-canvas-inset';
}

function textToneClass(tone: DecisionStateTone): string {
  if (tone === 'danger') return 'text-danger-fg';
  if (tone === 'warning') return 'text-accent-fg';
  if (tone === 'accent') return 'text-accent-fg';
  return 'text-fg-muted';
}

export function DecisionStateStrip({ items }: { items: DecisionStateItem[] }) {
  if (items.length === 0) return null;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      className="mx-5"
      style={{ flexGrow: 0, flexShrink: 0 }}
      contentContainerStyle={{ flexDirection: 'row', alignItems: 'flex-start', gap: 6, paddingRight: 20 }}
    >
      {items.map((item) => {
        const containerClasses = containerToneClass(item.tone);
        const textClasses = textToneClass(item.tone);
        return (
          <View
            key={item.id}
            className={`flex-row items-baseline gap-x-1.5 rounded-sm border px-2 py-1 ${containerClasses}`}
            style={{ maxWidth: 180, flexShrink: 0 }}
          >
            {item.label ? (
              <Text
                className={`font-sans-semibold text-caption ${textClasses}`}
                numberOfLines={1}
              >
                {item.label}
              </Text>
            ) : null}
            <Text
              className={`font-sans-medium text-caption ${textClasses}`}
              numberOfLines={1}
              style={{ flexShrink: 1, minWidth: 0 }}
            >
              {item.text}
            </Text>
          </View>
        );
      })}
    </ScrollView>
  );
}
