import { Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';
import { Record } from './Record';
import { Item, Row } from './Row';
import { useDialog } from './useDialog';

// What stays fixed through a chapter, or shows again on the roll card, waits behind the name (ui.md 2.1).
function Sheet({ player, journal, onGrowth, onClose }: {
  player: GameView['player']; journal: GameView['journal']; onGrowth?: () => void; onClose: () => void;
}) {
  const ref = useDialog(onClose);
  return (
    <View ref={ref} accessibilityRole={'dialog' as never}
      className="absolute left-3 right-3 top-full z-20 rounded-md border border-border-strong bg-canvas-floating py-1">
      <Row inset label={ko.row.ability}>
        {player.approaches.map((a) => <Item key={a.id}>{a.name} {a.value}</Item>)}
        {onGrowth ? (
          <Pressable accessibilityRole="button" onPress={onGrowth} className="rounded-sm border border-gold-fg px-1">
            <Item tone="gold">{ko.growth(player.growth)}</Item>
          </Pressable>
        ) : null}
      </Row>
      <Row inset label={ko.traits}>
        {player.traits.map((t) => <Item key={t.id} dim={t.spent}>{t.name}{t.spent ? ko.spent : ''}</Item>)}
      </Row>
      {player.things.length ? (
        <Row inset label={ko.row.carried}>
          {player.things.map((x) => <Item key={x.id} color={colors.kind.thing}>{x.name}</Item>)}
        </Row>
      ) : null}
      <Record inset journal={journal} />
    </View>
  );
}

function Chevron({ up }: { up: boolean }) {
  return (
    <View style={{ width: 6, height: 6, borderRightWidth: 1.5, borderBottomWidth: 1.5,
      marginTop: up ? 3 : -3, transform: [{ rotate: up ? '225deg' : '45deg' }] }} className="border-fg-subtle" />
  );
}

export function Self({ player, journal, open, onToggle, onGrowth }: {
  player: GameView['player']; journal: GameView['journal']; open: boolean; onToggle?: () => void; onGrowth?: () => void;
}) {
  const name = player.name || ko.hero;
  return (
    <View className="z-20">
      <Row label={(
        <Pressable accessibilityRole="button" accessibilityLabel={name} accessibilityState={{ expanded: open, disabled: !onToggle }}
          disabled={!onToggle} onPress={onToggle} className="flex-row items-center gap-1.5 pr-2">
          <Text className={`font-sans-semibold text-chip ${open ? 'text-gold-fg' : 'text-fg-default'}`}>{name}</Text>
          {onGrowth ? <View className="h-[6px] w-[6px] rounded-full bg-gold-fg" /> : null}
          <Chevron up={open} />
        </Pressable>
      )}>
        <View className="flex-row items-center gap-1">
          <Item tone="muted">{ko.health}</Item>
          <Boxes fill={player.wound_boxes - player.wounds} boxes={player.wound_boxes} />
        </View>
        {player.tags.map((t) => (
          <Item key={`tag${t.slot}`} tone={t.kind === 'edge' ? 'gold' : 'danger'}>{t.name}</Item>
        ))}
      </Row>
      {open ? <Sheet player={player} journal={journal} onGrowth={onGrowth} onClose={() => onToggle?.()} /> : null}
    </View>
  );
}
