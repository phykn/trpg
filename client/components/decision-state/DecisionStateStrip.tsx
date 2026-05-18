import { Text, View } from 'react-native';

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
    <View className="mx-5 flex-row gap-1.5">
      {items.map((item) => {
        const containerClasses = containerToneClass(item.tone);
        const textClasses = textToneClass(item.tone);
        return (
          <View
            key={item.id}
            className={`min-w-0 flex-1 rounded-sm border px-2 py-1.5 ${containerClasses}`}
          >
            <Text
              className={`font-sans-semibold text-caption ${textClasses}`}
              numberOfLines={1}
            >
              {item.label}
            </Text>
            <Text
              className={`font-sans-medium text-caption ${textClasses}`}
              numberOfLines={1}
            >
              {item.text}
            </Text>
          </View>
        );
      })}
    </View>
  );
}
