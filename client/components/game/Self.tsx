import { Pressable, Text, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { IconButton } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { useEnter } from '@/components/ui/motion';
import { useDialog } from '@/components/ui/useDialog';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Item, Row } from './Row';

// Health counts what is left, so it must not look like a clock's boxes, which count what has gone wrong.
// The sheet's row already leads with the heart, so only the button draws its own.
function Health({ left, of, bare }: { left: number; of: number; bare?: boolean }) {
  return (
    <View className="flex-row items-center gap-[3px]">
      {bare ? null : <View className="mr-0.5"><Icon name="heart" size={12} color={colors.health.fg} width={2.2} /></View>}
      {Array.from({ length: of }, (_, i) => (
        <View key={i} className="h-2 w-2 rounded-full border"
          style={{ borderColor: colors.health.fg, backgroundColor: i < left ? colors.health.fg : 'transparent' }} />
      ))}
    </View>
  );
}

// Health is the one hero fact always on screen; the rest waits behind the button.
export function HeroButton({ player, open, growth, onPress }: {
  player: GameView['player']; open: boolean; growth: boolean; onPress?: () => void;
}) {
  const name = player.name || ko.hero;
  const left = player.wound_boxes - player.wounds;
  return (
    <IconButton icon="user" label={ko.heroButton(name, left, player.wound_boxes)} open={open} dot={growth} onPress={onPress}>
      <Health left={left} of={player.wound_boxes} />
    </IconButton>
  );
}

// Ordered by how often a sentence needs it: condition first, then what rolls lean on, then the record.
export function HeroSheet({ player, journal, onGrowth, onClose }: {
  player: GameView['player']; journal: GameView['journal']; onGrowth?: () => void; onClose: () => void;
}) {
  const ref = useDialog(onClose);
  const enter = useEnter(-6);
  const owes = journal.owes;
  const beliefs = journal.beliefs.filter((b) => b.here);
  return (
    <Animated.View style={[{ position: 'absolute', left: 12, right: 12, top: '100%', zIndex: 20 }, enter]}>
      <View ref={ref} accessibilityRole={'dialog' as never}
        className="rounded-2xl border border-border-strong bg-canvas-floating py-2">
        <View className="h-9 flex-row items-center px-3">
          <Text className="min-w-0 flex-1 font-sans-semibold text-body text-fg-default">{player.name || ko.hero}</Text>
          {onGrowth ? (
            <Pressable accessibilityRole="button" accessibilityLabel={ko.growth} onPress={onGrowth}
              className="h-7 flex-row items-center gap-1 rounded-full bg-gold-fg px-2.5">
              <Icon name="spark" size={12} color={colors.fg['on-emphasis']} width={2.2} />
              <Text className="font-sans-semibold text-chip text-fg-on-emphasis">{player.growth}</Text>
            </Pressable>
          ) : null}
        </View>
        <Row inset icon="heart" tone={colors.health.fg} label={ko.health}>
          <View className="h-[22px] justify-center"><Health bare left={player.wound_boxes - player.wounds} of={player.wound_boxes} /></View>
        </Row>
        {player.tags.length ? (
          <Row inset icon="tag" label={ko.row.state}>
            {player.tags.map((t) => (
              <Item key={`tag${t.slot}`} color={t.kind === 'edge' ? colors.gold.fg : colors.danger.fg}>{t.name}</Item>
            ))}
          </Row>
        ) : null}
        <Row inset icon="bolt" label={ko.row.ability}>
          {player.approaches.map((a) => (
            <Item key={a.id}>{a.name} <Text className="font-mono-medium text-chip-stat">{a.value}</Text></Item>
          ))}
        </Row>
        <Row inset icon="star" label={ko.traits}>
          {player.traits.map((t) => <Item key={t.id} dim={t.spent}>{t.name}</Item>)}
        </Row>
        {player.things.length ? (
          <Row inset icon="bag" label={ko.row.carried}>
            {player.things.map((x) => <Item key={x.id} color={colors.kind.thing}>{x.name}</Item>)}
          </Row>
        ) : null}
        {owes.length || beliefs.length ? (
          <Row inset icon="book" label={ko.row.record}>
            {owes.map((o) => (
              <Item key={`${o.debtor}${o.creditor}${o.kind}`} color={colors.gold.fg}>
                {o.kind === 'promise' ? ko.promise(o.name, o.promise) : ko.kindness(o.name)}
              </Item>
            ))}
            {beliefs.map((b) => <Item key={b.id} color={colors.fg.muted}>{b.text}</Item>)}
          </Row>
        ) : null}
      </View>
    </Animated.View>
  );
}
