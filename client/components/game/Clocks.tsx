import { View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';
import { Item, Row } from './Row';

export function Clocks({ clocks, crisis }: { clocks: GameView['clocks']; crisis?: string[] }) {
  if (!clocks.length) return null;
  return (
    <View className="pb-1">
      <Row label={ko.row.danger}>
          {clocks.map((c) => (
            <View key={c.id} className="flex-row items-center gap-1">
              <Item tone="danger">{c.name}</Item>
              <Boxes fill={c.fill} boxes={c.boxes} tone="danger" />
              {crisis?.includes(c.id) ? <Item tone="gold">{ko.crisis}</Item> : null}
            </View>
          ))}
      </Row>
    </View>
  );
}
