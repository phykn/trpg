import { View } from 'react-native';
import { colors } from '@/design/tokens';
import { ChipTab } from './ChipTab';
import { IconButton, ICON_PATH } from './IconButton';
import { PanelBody } from './PanelBody';
import type { PanelSlot } from '@/types/ui';

export function ContextCard({ slots, activeId, onSelect, onCollapse }: {
  slots: PanelSlot[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCollapse?: () => void;
}) {
  const activeSlot = slots.find((s) => s.id === activeId) ?? null;
  const panel = activeSlot?.panel ?? null;

  return (
    <View className="mx-5 bg-canvas-subtle border border-border-default rounded-md">
      <View
        className="flex-row p-2 gap-0.5 items-center"
        style={panel ? { borderBottomWidth: 1, borderBottomColor: colors.border.default } : undefined}
      >
        <IconButton d={ICON_PATH.chevronUp} onPress={onCollapse} />
        <View className="flex-1 flex-row gap-0.5">
          {slots.map((s) => (
            <ChipTab
              key={s.id}
              chip={s.chip}
              active={s.id === activeId}
              onPress={() => onSelect(s.id)}
            />
          ))}
        </View>
        <IconButton d={ICON_PATH.menu} />
      </View>
      {panel && <PanelBody panel={panel} />}
    </View>
  );
}
