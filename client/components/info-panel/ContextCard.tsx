import React from 'react';
import { ScrollView, View } from 'react-native';

import { Chip, Surface } from '@/components/ui';

import type { PanelAction, PanelSlot } from '@/logic/info-panel/types';
import { compose } from '@/locale/ko';
import { PanelBody } from './PanelBody';

const CONTEXT_PANEL_MAX_HEIGHT = 260;

export function ContextCard({ slots, activeId, onSelect, onAction, actionDisabled = false, leading, trailing }: {
  slots: PanelSlot[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
  leading?: React.ReactNode;
  trailing?: React.ReactNode;
}) {
  const panel = slots.find((s) => s.id === activeId)?.panel ?? null;

  return (
    <View
      className="mx-5"
      style={{ zIndex: 10, pointerEvents: 'box-none' }}
    >
      <View
        className="flex-row gap-2 items-center"
      >
        {leading}
        <View className="flex-1 flex-row gap-1">
          {slots.map((s) => (
            <Chip
              key={s.id}
              variant="tab"
              label={s.chip.short}
              active={s.id === activeId}
              dot={s.chip.dot}
              dotAccessibilityLabel={compose.changedNotice(s.chip.short)}
              onPress={() => onSelect(s.id)}
            />
          ))}
        </View>
        {trailing}
      </View>
      {panel && (
        <Surface
          variant="floating"
          className="absolute left-0 right-0 top-10 overflow-hidden"
          style={{ maxHeight: CONTEXT_PANEL_MAX_HEIGHT, zIndex: 20 }}
        >
          <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
            <PanelBody
              panel={panel}
              onAction={onAction}
              actionDisabled={actionDisabled}
            />
          </ScrollView>
        </Surface>
      )}
    </View>
  );
}
