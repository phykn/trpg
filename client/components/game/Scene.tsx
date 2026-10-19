import { View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';
import { Item, Row } from './Row';

export function Scene({ scene, beats, beatsMax }: { scene: GameView['scene']; beats: number; beatsMax: number }) {
  const around = scene.people.length + scene.things.length + scene.obstacles.length + scene.tags.length;
  return (
    <>
      {around ? (
        <Row label={ko.row.around}>
          {scene.people.map((p) => <Item key={p.id} color={colors.kind.person}>{p.name}</Item>)}
          {scene.things.map((x) => <Item key={x.id} color={colors.kind.thing}>{x.name}</Item>)}
          {scene.obstacles.map((o) => (
            <View key={o.id} className="flex-row items-center gap-1">
              <Item color={colors.kind.obstacle}>{o.name}</Item>
              <Boxes fill={o.fill} boxes={o.boxes} />
            </View>
          ))}
          {scene.tags.map((t) => <Item key={`${t.owner}${t.slot}`} tone={t.kind === 'edge' ? 'gold' : 'danger'}>{t.name}</Item>)}
        </Row>
      ) : null}
      <Row label={ko.row.here}>
        <Item>{scene.place.name}</Item>
        <View className="flex-row items-center gap-1">
          <Item tone="muted">{ko.beats}</Item>
          <Boxes fill={beats} boxes={beatsMax} tone="time" />
        </View>
      </Row>
      {scene.exits.length ? (
        <Row label={ko.row.exits}>
          {scene.exits.map((e) => <Item key={e.id} dim={e.blocked}>{e.name}{e.blocked ? ko.blockedExit : ''}</Item>)}
        </Row>
      ) : null}
    </>
  );
}
