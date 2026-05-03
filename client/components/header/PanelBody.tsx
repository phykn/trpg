import React from 'react';
import { ScrollView, View, Text } from 'react-native';
import { Chip, Expandable, StatRow, InlineParts, InlineNodes, LabeledRow, Row, ExpandGroup, ExpandableTitle } from '@/components/ui';
import { toneColor } from '@/design/tokens';
import type { MetaSegment, Panel, PanelAction, PanelActions } from '@/types/ui';

const META_LINE_HEIGHT = 18;
const META_CLASS = 'font-sans text-caption italic text-right text-fg-muted';

function ExpandableMeta({ segments }: { segments: MetaSegment[] }) {
  const metaKey = segments.map((s) => `${s.text}|${s.tone ?? ''}`).join('::');
  const measureText = segments.map((s) => s.text).join('');
  return (
    <Expandable
      contentKey={metaKey}
      lineHeight={META_LINE_HEIGHT}
      textClassName={META_CLASS}
      measureText={measureText}
    >
      {segments.map((seg, i) =>
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
    </Expandable>
  );
}

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
            <Chip
              key={it.label}
              variant="action"
              label={it.label}
              onPress={() => onAction?.(it)}
            />
          ))}
        </ScrollView>
      )}
    </View>
  );
}

export function PanelBody({ panel, onAction }: {
  panel: Panel;
  onAction?: (action: PanelAction) => void;
}) {
  if (panel.empty) {
    return (
      <View className="px-4 py-10 items-center justify-center" style={{ minHeight: 120 }}>
        <Text className="font-sans text-caption text-fg-subtle">
          비어 있음
        </Text>
      </View>
    );
  }

  const sections = panel.sections || [];

  return (
    <View className="px-4 py-3 gap-2.5" style={{ minHeight: 160 }}>
      <View className="flex-row items-center gap-2" style={{ minHeight: 22 }}>
        <ExpandableTitle text={panel.title} />
        {panel.meta && panel.meta.length > 0 && (
          <View className="flex-1 min-w-0">
            <ExpandableMeta segments={panel.meta} />
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
        {sections.map((section) => (
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
