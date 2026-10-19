import { Pressable, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';
import { Item, Row } from './Row';

/** Approaches, wounds, beats, traits (spent ones dim), tags and scars, growth waiting. */
export function Self({ player, onGrowth }: { player: GameView['player']; onGrowth?: () => void }) {
  return (
    <Row>
      {player.approaches.map((a) => <Item key={a.id}>{a.name}{a.value}</Item>)}
      <View className="flex-row items-center gap-1">
        <Item tone="muted">{ko.wounds}</Item>
        <Boxes fill={player.wounds} boxes={player.wound_boxes} />
      </View>
      <Item tone="muted">{ko.beats}{player.beats}/{player.beats_max}</Item>
      {player.traits.map((t) => <Item key={t.id} dim={t.spent}>{t.name}{t.spent ? ko.spent : ''}</Item>)}
      {player.tags.map((t) => (
        <Item key={`tag${t.slot}`} tone={t.kind === 'edge' ? 'gold' : 'danger'}>{t.name}</Item>
      ))}
      {player.things.map((x) => <Item key={x.id} tone="muted">{x.name}</Item>)}
      {onGrowth ? (
        <Pressable accessibilityRole="button" onPress={onGrowth} className="rounded-sm border border-gold-fg px-1">
          <Item tone="gold">{ko.growth(player.growth)}</Item>
        </Pressable>
      ) : null}
    </Row>
  );
}
