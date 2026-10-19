import { Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';
import { Record } from './Record';
import { Group, Item, Row } from './Row';
import { useDialog } from './useDialog';

// What stays fixed through a chapter, or shows again on the roll card, waits behind the name (ui.md 2.1).
function Sheet({ player, journal, onGrowth, onClose }: {
  player: GameView['player']; journal: GameView['journal']; onGrowth?: () => void; onClose: () => void;
}) {
  const ref = useDialog(onClose);
  return (
    <View ref={ref} accessibilityRole={'dialog' as never}
      className="absolute left-3 right-3 top-full z-20 rounded-md border border-border-strong bg-canvas-floating py-1">
      <Row label={ko.row.ability}>
        {player.approaches.map((a) => <Item key={a.id}>{a.name} {a.value}</Item>)}
        {onGrowth ? (
          <Pressable accessibilityRole="button" onPress={onGrowth} className="rounded-sm border border-gold-fg px-1">
            <Item tone="gold">{ko.growth(player.growth)}</Item>
          </Pressable>
        ) : null}
      </Row>
      <Row label={ko.traits}>
        {player.traits.map((t) => <Item key={t.id} dim={t.spent}>{t.name}{t.spent ? ko.spent : ''}</Item>)}
      </Row>
      {player.things.length ? (
        <Row label={ko.row.carried}>
          {player.things.map((x) => <Item key={x.id} color={colors.kind.thing}>{x.name}</Item>)}
        </Row>
      ) : null}
      <Record journal={journal} />
    </View>
  );
}

export function Self({ player, journal, open, onToggle, onGrowth }: {
  player: GameView['player']; journal: GameView['journal']; open: boolean; onToggle?: () => void; onGrowth?: () => void;
}) {
  return (
    <View className="z-20">
      <Group>
        <View className="flex-row items-start px-4 py-0.5" style={{ columnGap: 10 }}>
          <Pressable accessibilityRole="button" accessibilityLabel={player.name || ko.hero} accessibilityState={{ expanded: open, disabled: !onToggle }}
            disabled={!onToggle} onPress={onToggle}
            className={`flex-row items-center gap-1 rounded-sm px-1 ${open ? 'bg-accent-muted' : ''}`} style={{ marginLeft: -4 }}>
            <Text className="font-sans-semibold text-chip text-fg-default">{player.name || ko.hero}</Text>
            {onGrowth ? <View className="h-[6px] w-[6px] rounded-full bg-gold-fg" /> : null}
            <Text className="font-sans text-chip text-fg-subtle">{open ? '▴' : '▾'}</Text>
          </Pressable>
          <View className="min-w-0 flex-1 flex-row flex-wrap items-center" style={{ columnGap: 10, rowGap: 2 }}>
            <View className="flex-row items-center gap-1">
              <Item tone="muted">{ko.wounds}</Item>
              <Boxes fill={player.wounds} boxes={player.wound_boxes} />
            </View>
            {player.tags.map((t) => (
              <Item key={`tag${t.slot}`} tone={t.kind === 'edge' ? 'gold' : 'danger'}>{t.name}</Item>
            ))}
          </View>
        </View>
      </Group>
      {open ? <Sheet player={player} journal={journal} onGrowth={onGrowth} onClose={() => onToggle?.()} /> : null}
    </View>
  );
}
