import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { shadow } from '@/design/tokens';
import type { PanelSlot } from '@/types/ui';

import { ChipTab } from './ChipTab';
import { IconButton, ICON_PATH } from './IconButton';
import { PanelBody } from './PanelBody';

export function ContextCard({ slots, activeId, onSelect, onCollapse, onNewGame }: {
  slots: PanelSlot[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCollapse?: () => void;
  onNewGame?: () => void;
}) {
  const activeSlot = slots.find((s) => s.id === activeId) ?? null;
  const panel = activeSlot?.panel ?? null;
  const [menuOpen, setMenuOpen] = React.useState(false);

  return (
    <View className="mx-5" style={{ zIndex: 10 }}>
      <View
        className="bg-canvas-subtle border border-border-default rounded-md flex-row p-2 gap-1 items-center"
        style={shadow.paper}
      >
        <IconButton d={ICON_PATH.chevronUp} onPress={onCollapse} />
        <View className="flex-1 flex-row gap-1">
          {slots.map((s) => (
            <ChipTab
              key={s.id}
              chip={s.chip}
              active={s.id === activeId}
              onPress={() => onSelect(s.id)}
            />
          ))}
        </View>
        <IconButton d={ICON_PATH.menu} onPress={() => setMenuOpen((v) => !v)} />
      </View>
      {panel && (
        <View
          className="bg-canvas-subtle border border-border-default rounded-md"
          style={{ position: 'absolute', top: '100%', left: 0, right: 0, marginTop: 4, ...shadow.floating }}
        >
          <PanelBody panel={panel} />
        </View>
      )}
      {menuOpen && (
        <View
          className="bg-canvas-subtle border border-border-default rounded-md"
          style={{ position: 'absolute', top: '100%', right: 0, marginTop: 4, minWidth: 140, zIndex: 20, ...shadow.floating }}
        >
          <Pressable
            onPress={() => {
              setMenuOpen(false);
              onNewGame?.();
            }}
            className="px-3 py-2.5"
          >
            <Text className="font-sans text-body text-fg-default">새 게임</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}
