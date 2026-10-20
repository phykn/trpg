import { View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';
import { Item, Row } from './Row';

// Deadlines, threats and forks draw closer at every scene end, so their next box shows the scene's time spent;
// risk clocks move only on failures and show none.
export function Clocks({ clocks, crisis, time = 0 }: { clocks: GameView['clocks']; crisis?: string[]; time?: number }) {
  if (!clocks.length) return null;
  return (
    <Row icon="alert" tone={colors.danger.fg} label={ko.row.danger}>
      {clocks.map((c) => (
        <View key={c.id} className="flex-row items-center gap-1.5">
          <Item color={colors.danger.fg}>{c.name}</Item>
          <Boxes fill={c.fill} boxes={c.boxes} tone="danger" part={c.kind === 'clock' ? 0 : time} />
          {crisis?.includes(c.id) ? <Item strong color={colors.gold.fg}>{ko.crisis}</Item> : null}
        </View>
      ))}
    </Row>
  );
}
