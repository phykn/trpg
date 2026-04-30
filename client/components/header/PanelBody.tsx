import React from 'react';
import { ScrollView, View, Text, Pressable } from 'react-native';
import { StatRow, InlineParts, InlineNodes, LabeledRow, Row, ExpandGroup } from '@/components/ui';
import { toneColor } from '@/design/tokens';
import type { Panel, PanelAction, PanelActions } from '@/types/ui';

function ActionScroller({ group, onAction }: {
  group: PanelActions;
  onAction?: (action: PanelAction) => void;
}) {
  const [width, setWidth] = React.useState(0);
  return (
    <View
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
      style={{ flex: 1, minWidth: 0 }}
    >
      {width > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={{ width }}
          contentContainerStyle={{ flexDirection: 'row', gap: 6, paddingRight: 8 }}
        >
          {group.items.map((it) => (
            <Pressable
              key={it.label}
              onPress={() => onAction?.(it)}
              className="shrink-0 px-2 py-1 rounded-sm border border-border-default bg-canvas-default active:bg-canvas-inset"
            >
              <Text numberOfLines={1} className="font-sans text-panel text-fg-default">{it.label}</Text>
            </Pressable>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

export function PanelBody({ panel, onAction }: { panel: Panel; onAction?: (action: PanelAction) => void }) {
  return (
    <View className="px-4 py-3 gap-2.5" style={{ minHeight: 160 }}>
      <View className="flex-row items-center gap-2" style={{ minHeight: 22 }}>
        <View className="flex-1 min-w-0">
          <Text numberOfLines={1} className="font-serif-medium text-title text-fg-default">
            {panel.title}
          </Text>
        </View>
        {panel.meta && panel.meta.length > 0 && (
          <View className="flex-1 min-w-0">
            <Text
              numberOfLines={1}
              className="font-sans text-caption italic text-right text-fg-muted"
            >
              {panel.meta.map((seg, i) =>
                seg.tone ? (
                  <Text
                    key={i}
                    className="font-sans-semibold"
                    style={{ color: toneColor[seg.tone] }}
                  >
                    {seg.text}
                  </Text>
                ) : (
                  <Text key={i}>{seg.text}</Text>
                ),
              )}
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
          <LabeledRow
            key={section.label}
            label={section.label}
            mono={!!section.nodes}
            clampLines={section.clampLines}
          >
            {section.nodes ? <InlineNodes entries={section.nodes} /> : section.text}
          </LabeledRow>
        ))}
      </ExpandGroup>

      {(panel.actions || []).map((group) =>
        group.items.length > 0 ? (
          <Row key={group.label} label={group.label} variableHeight>
            <ActionScroller group={group} onAction={onAction} />
          </Row>
        ) : (
          <LabeledRow key={group.label} label={group.label}>—</LabeledRow>
        ),
      )}
    </View>
  );
}
