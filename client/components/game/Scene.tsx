import { View } from 'react-native';

import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';
import { Item, Row } from './Row';

/** People (attitude), things, obstacles (boxes), place tags and the ways out. */
export function Scene({ scene }: { scene: GameView['scene'] }) {
  return (
    <Row>
      {scene.people.map((p) => <Item key={p.id}>{p.name}({p.attitude})</Item>)}
      {scene.things.map((x) => <Item key={x.id}>{x.name}</Item>)}
      {scene.obstacles.map((o) => (
        <View key={o.id} className="flex-row items-center gap-1">
          <Item>{o.name}</Item>
          <Boxes fill={o.fill} boxes={o.boxes} />
        </View>
      ))}
      {scene.tags.map((t) => <Item key={`${t.owner}${t.slot}`} tone={t.kind === 'edge' ? 'gold' : 'danger'}>{t.name}</Item>)}
      {scene.exits.map((e) => <Item key={e.id} tone="muted" dim={e.blocked}>→ {e.name}</Item>)}
    </Row>
  );
}
