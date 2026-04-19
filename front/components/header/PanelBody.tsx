import { View, Text } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';
import { StatRow, InlineNodes, LabeledRow } from '@/components/atoms';
import type { Panel } from '@/types/game';

export function PanelBody({ panel }: { panel: Panel }) {
  return (
    <View style={{
      paddingHorizontal: Theme.space.md + 2, paddingVertical: Theme.space.md,
      minHeight: 164,
      gap: Theme.space.sm + 2,
    }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: Theme.space.sm, height: 22 }}>
        <Text numberOfLines={1} style={{
          fontFamily: Theme.fonts.serifMedium,
          ...typeStyle('title'),
          color: Theme.text, flex: 1,
        }}>{panel.title}</Text>
        {panel.meta && (
          <Text style={{
            ...typeStyle('caption'),
            color: Theme.textDim, fontStyle: 'italic', flexShrink: 0,
            fontFamily: Theme.fonts.sansRegular,
          }}>{panel.meta}</Text>
        )}
      </View>

      {panel.bar && <StatRow {...panel.bar} />}
      {panel.barSplit && (
        <View style={{ flexDirection: 'row', gap: Theme.space.md + 2 }}>
          {panel.barSplit.map((b, i) => (
            <View key={i} style={{ flex: 1, minWidth: 0 }}><StatRow {...b} /></View>
          ))}
        </View>
      )}

      {(panel.sections || []).map((section, si) => (
        <LabeledRow key={si} label={section.label} mono={!!section.nodes}>
          {section.nodes ? <InlineNodes entries={section.nodes} /> : section.text}
        </LabeledRow>
      ))}
    </View>
  );
}
