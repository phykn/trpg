import { Text, View } from 'react-native';

import type { DecisionStateItem, DecisionStateTone } from '@/logic/decision-state/types';

function containerToneClass(tone: DecisionStateTone): string {
  if (tone === 'danger') return 'border-danger-fg bg-canvas-subtle';
  if (tone === 'warning') return 'border-accent-fg bg-canvas-subtle';
  if (tone === 'accent') return 'border-accent-fg bg-accent-muted';
  if (tone === 'level' || tone === 'hp' || tone === 'mp') return 'border-border-default bg-canvas-inset';
  return 'border-border-default bg-canvas-inset';
}

function textToneClass(tone: DecisionStateTone): string {
  if (tone === 'danger') return 'text-danger-fg';
  if (tone === 'warning') return 'text-accent-fg';
  if (tone === 'accent') return 'text-accent-fg';
  if (tone === 'level') return 'text-exp-fg';
  if (tone === 'hp') return 'text-hp-fg';
  if (tone === 'mp') return 'text-mp-fg';
  return 'text-fg-muted';
}

export function DecisionStateStrip({ items }: { items: DecisionStateItem[] }) {
  if (items.length === 0) return null;

  return (
    <View
      className="mx-5"
      style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-start', gap: 6, flexGrow: 0, flexShrink: 0 }}
    >
      {items.map((item) => {
        const containerClasses = containerToneClass(item.tone);
        const textClasses = textToneClass(item.tone);
        const accessibilityLabel = item.label ? `${item.label} ${item.text}` : item.text;
        return (
          <View
            key={item.id}
            accessibilityLabel={accessibilityLabel}
            className={`flex-row items-baseline gap-x-1.5 overflow-hidden rounded-sm border px-2 py-1 ${containerClasses}`}
            style={{ maxWidth: 180, flexShrink: 1 }}
          >
            {item.progress !== undefined ? (
              <View
                className="absolute inset-y-0 left-0 bg-exp-fg opacity-20"
                style={{ width: `${Math.round(item.progress * 100)}%` }}
              />
            ) : null}
            {item.label ? (
              <Text
                className={`font-sans-semibold text-caption ${textClasses}`}
                numberOfLines={1}
                ellipsizeMode="tail"
              >
                {item.label}
              </Text>
            ) : null}
            <Text
              className={`font-sans-medium text-caption ${textClasses}`}
              numberOfLines={1}
              ellipsizeMode="tail"
              style={{ flexShrink: 1, minWidth: 0 }}
            >
              {item.text}
            </Text>
          </View>
        );
      })}
    </View>
  );
}
