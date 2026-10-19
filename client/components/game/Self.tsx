import { Pressable, View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';
import { Group, Item, Row } from './Row';

export function Self({ player, onGrowth }: { player: GameView['player']; onGrowth?: () => void }) {
  return (
    <Group>
      <Row label={ko.row.ability}>
        {player.approaches.map((a) => <Item key={a.id}>{a.name} {a.value}</Item>)}
        {onGrowth ? (
          <Pressable accessibilityRole="button" onPress={onGrowth} className="rounded-sm border border-gold-fg px-1">
            <Item tone="gold">{ko.growth(player.growth)}</Item>
          </Pressable>
        ) : null}
      </Row>
      <Row label={ko.row.state}>
        <View className="flex-row items-center gap-1">
          <Item tone="muted">{ko.wounds}</Item>
          <Boxes fill={player.wounds} boxes={player.wound_boxes} />
        </View>
        {player.tags.map((t) => (
          <Item key={`tag${t.slot}`} tone={t.kind === 'edge' ? 'gold' : 'danger'}>{t.name}</Item>
        ))}
      </Row>
      <Row label={ko.traits}>
        {player.traits.map((t) => <Item key={t.id} dim={t.spent}>{t.name}{t.spent ? ko.spent : ''}</Item>)}
      </Row>
      {player.things.length ? (
        <Row label={ko.row.carried}>{player.things.map((x) => <Item key={x.id} color={colors.kind.thing}>{x.name}</Item>)}</Row>
      ) : null}
    </Group>
  );
}
