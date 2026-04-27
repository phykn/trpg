import { View, Text } from 'react-native';
import { StatRow, InlineParts, InlineNodes, LabeledRow, ExpandGroup } from '@/components/ui';
import type { Panel } from '@/types/ui';

export function PanelBody({ panel }: { panel: Panel }) {
  return (
    <View className="px-4 py-3 gap-2.5" style={{ minHeight: 160 }}>
      <View className="flex-row items-center gap-2" style={{ minHeight: 22 }}>
        <View className="flex-1 min-w-0">
          <Text numberOfLines={1} className="font-serif-medium text-title text-fg-default">
            {panel.title}
          </Text>
        </View>
        {panel.meta && (
          <View className="flex-1 min-w-0">
            <Text
              numberOfLines={1}
              className="font-sans text-caption text-fg-muted italic text-right"
            >
              {panel.meta}
            </Text>
          </View>
        )}
      </View>

      {panel.bar && <StatRow {...panel.bar} />}
      {panel.barSplit && (
        <View className="flex-row gap-4">
          {panel.barSplit.map((cell) => (
            <View key={cell.label} className="flex-1 min-w-0">
              {'parts' in cell
                ? <InlineParts label={cell.label} parts={cell.parts} />
                : <StatRow {...cell} />}
            </View>
          ))}
        </View>
      )}

      <ExpandGroup>
        {(panel.sections || []).map((section) => (
          <LabeledRow key={section.label} label={section.label} mono={!!section.nodes}>
            {section.nodes ? <InlineNodes entries={section.nodes} /> : section.text}
          </LabeledRow>
        ))}
      </ExpandGroup>
    </View>
  );
}
