import React from 'react';
import { Pressable, ScrollView, View, Text } from 'react-native';
import { Chip, Expandable, Glyph, StatRow, InlineParts, InlineNodes, LabeledRow, Row, ExpandGroup, ExpandableTitle } from '@/components/ui';
import { colors, toneColor } from '@/design/tokens';
import type { MetaSegment, Panel, PanelAction, PanelActions } from '@/logic/info-panel/types';
import { ko } from '@/locale/ko';

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

function ActionScroller({ group, onAction, actionDisabled = false }: {
  group: PanelActions;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
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
              disabled={actionDisabled}
            />
          ))}
        </ScrollView>
      )}
    </View>
  );
}

function HeaderTitleGroup({ panel }: { panel: Panel }) {
  return (
    <View
      className="flex-row items-center gap-2"
      style={{ minWidth: 0, flexShrink: 1 }}
    >
      <ExpandableTitle text={panel.title} pressableClassName="shrink min-w-0" />
      {panel.titleAction && (
        <Pressable
          onPress={panel.titleAction.onPress}
          accessibilityRole="button"
          accessibilityLabel={panel.titleAction.label}
          style={{
            paddingHorizontal: 10,
            paddingVertical: 4,
            borderRadius: 2,
            backgroundColor: colors.accent.muted,
            borderWidth: 1,
            borderColor: colors.accent.fg,
            flexShrink: 0,
          }}
        >
          <Text className="font-sans-semibold text-caption" style={{ color: colors.accent.fg, letterSpacing: 0.6 }}>
            {panel.titleAction.label}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

export function PanelBody({ panel, onAction, actionDisabled = false }: {
  panel: Panel;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
}) {
  if (panel.empty) {
    return (
      <View
        className="px-4 py-10 items-center justify-center gap-2"
        style={{ minHeight: 120 }}
      >
        <Glyph kind="outline" tone="subtle" size={16} />
        <Text className="font-sans text-caption text-fg-subtle">
          {ko.empty.panel}
        </Text>
      </View>
    );
  }

  const sections = panel.sections || [];
  const showHeader = panel.title.length > 0 || !!panel.titleAction || !!(panel.meta && panel.meta.length > 0);

  return (
    <View className="px-4 py-3 gap-2.5" style={{ minHeight: 160 }}>
      {showHeader && (
        <View className="flex-row items-center gap-2" style={{ minHeight: 22 }}>
          <HeaderTitleGroup panel={panel} />
          {panel.meta && panel.meta.length > 0 && (
            <View className="flex-1 min-w-0">
              <ExpandableMeta segments={panel.meta} />
            </View>
          )}
        </View>
      )}

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
            mono={section.mono || !!section.nodes}
            clampLines={section.clampLines}
          >
            {section.nodes ? <InlineNodes entries={section.nodes} /> : section.text}
          </LabeledRow>
        ))}
      </ExpandGroup>

      {(panel.actions || []).map((group) =>
        group.items.length > 0 ? (
          <Row key={group.label} label={group.label} variableHeight>
            <ActionScroller
              group={group}
              onAction={onAction}
              actionDisabled={actionDisabled}
            />
          </Row>
        ) : (
          <LabeledRow key={group.label} label={group.label}>—</LabeledRow>
        ),
      )}
    </View>
  );
}
