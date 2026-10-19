import { Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Record } from './Record';
import { Item, Row } from './Row';
import { useDialog } from './useDialog';

// Health counts what is left, so it must not look like a clock's boxes, which count what has gone wrong.
function Health({ left, of }: { left: number; of: number }) {
  return (
    <View className="flex-row items-center gap-[3px]">
      {Array.from({ length: of }, (_, i) => (
        <View key={i} className="h-[8px] w-[8px] rounded-full border"
          style={{ borderColor: colors.success.fg, backgroundColor: i < left ? colors.success.fg : 'transparent' }} />
      ))}
    </View>
  );
}

// Health is the one hero fact always on screen; the rest waits behind the icon (ui.md 2.1).
export function HeroIcon({ player, open, growth, onPress }: {
  player: GameView['player']; open: boolean; growth: boolean; onPress?: () => void;
}) {
  const name = player.name || ko.hero;
  const left = player.wound_boxes - player.wounds;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={ko.heroButton(name, left, player.wound_boxes)}
      accessibilityState={{ disabled: !onPress, expanded: open }} disabled={!onPress} onPress={onPress}
      className={`h-[24px] flex-row items-center gap-1.5 rounded-md pl-1.5 pr-1 ${open ? 'bg-accent-muted' : ''} ${onPress ? '' : 'opacity-40'}`}>
      <Health left={left} of={player.wound_boxes} />
      <View className="w-[16px] items-center">
        <View className="h-[7px] w-[7px] rounded-full border-[1.5px] border-fg-muted" />
        <View className="mt-[2px] h-[6px] w-[13px] rounded-t-full border-[1.5px] border-b-0 border-fg-muted" />
        {growth ? <View className="absolute -right-[2px] top-0 h-[6px] w-[6px] rounded-full bg-gold-fg" /> : null}
      </View>
    </Pressable>
  );
}

// Ordered by how often a sentence needs it: condition first, then what rolls lean on, then the record.
export function HeroSheet({ player, journal, onGrowth, onClose }: {
  player: GameView['player']; journal: GameView['journal']; onGrowth?: () => void; onClose: () => void;
}) {
  const ref = useDialog(onClose);
  return (
    <View ref={ref} accessibilityRole={'dialog' as never}
      className="absolute left-3 right-3 top-full z-20 rounded-md border border-border-strong bg-canvas-floating py-2">
        <Text className="px-4 pb-1 font-sans-semibold text-body text-fg-default">{player.name || ko.hero}</Text>
        <Row inset label={ko.health}>
          <Health left={player.wound_boxes - player.wounds} of={player.wound_boxes} />
        </Row>
        {player.tags.length ? (
          <Row inset label={ko.row.state}>
            {player.tags.map((t) => (
              <Item key={`tag${t.slot}`} tone={t.kind === 'edge' ? 'gold' : 'danger'}>{t.name}</Item>
            ))}
          </Row>
        ) : null}
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
