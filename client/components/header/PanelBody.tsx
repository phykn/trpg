import React from 'react';
import { ScrollView, View, Text, Pressable } from 'react-native';
import { StatRow, InlineParts, InlineNodes, LabeledRow, Row, ExpandGroup } from '@/components/ui';
import { colors, toneColor } from '@/design/tokens';
import type { Panel, PanelAction, PanelActions } from '@/types/ui';

function CornerMarks() {
  const SIZE = 14;
  const INSET = 8;
  const COLOR = colors.accent.fg;
  const OPACITY = 0.9;
  const corner = (v: 'top' | 'bottom', h: 'left' | 'right') => ({
    position: 'absolute' as const,
    width: SIZE,
    height: SIZE,
    opacity: OPACITY,
    [v]: INSET,
    [h]: INSET,
    [v === 'top' ? 'borderTopWidth' : 'borderBottomWidth']: 1,
    [h === 'left' ? 'borderLeftWidth' : 'borderRightWidth']: 1,
    borderColor: COLOR,
  });
  return (
    <>
      <View pointerEvents="none" style={corner('top', 'left')} />
      <View pointerEvents="none" style={corner('top', 'right')} />
      <View pointerEvents="none" style={corner('bottom', 'left')} />
      <View pointerEvents="none" style={corner('bottom', 'right')} />
    </>
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
            <Pressable
              key={it.label}
              onPress={() => onAction?.(it)}
              accessibilityRole="button"
              accessibilityLabel={it.label}
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

export function PanelBody({ panel, kind, onAction }: {
  panel: Panel;
  kind?: string;
  onAction?: (action: PanelAction) => void;
}) {
  const sections = panel.sections || [];
  const titleEmpty = !panel.title || panel.title === '—';
  const sectionsEmpty = sections.every(
    (s) => !(s.nodes ? s.nodes.length > 0 : s.text && s.text !== '—'),
  );
  const isEmptyPanel =
    titleEmpty &&
    sectionsEmpty &&
    !panel.bar &&
    !panel.barSplit &&
    (panel.actions || []).every((g) => g.items.length === 0);

  if (isEmptyPanel) {
    return (
      <View className="px-4 py-10 items-center justify-center" style={{ minHeight: 120 }}>
        <Text className="font-sans text-caption text-fg-subtle">
          아직 비어 있습니다
        </Text>
      </View>
    );
  }

  const showCorners = kind === 'bg';

  return (
    <View className="px-4 py-3 gap-2.5" style={{ minHeight: 160 }}>
      {showCorners && <CornerMarks />}
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
