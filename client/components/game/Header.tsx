import { Text, View } from 'react-native';

import { IconButton } from '@/components/ui/Button';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Item, Row } from './Row';
import { HeroButton, HeroSheet } from './Self';

export function Header({ view, menu, onMenu, hero, onHero, onGrowth }: {
  view: GameView; menu: boolean; onMenu?: () => void; hero: boolean; onHero?: () => void; onGrowth?: () => void;
}) {
  return (
    <View className="z-20 pb-0.5 pt-1">
      <View className="h-10 flex-row items-center pl-4 pr-2">
        <Text numberOfLines={1} className="min-w-0 flex-1 pr-2 font-sans-semibold text-body text-fg-default">
          <Text className="text-gold-fg">{ko.chapterNo(view.chapter.k)}</Text>  {view.chapter.title}
        </Text>
        <HeroButton player={view.player} open={hero} growth={!!onGrowth} onPress={onHero} />
        <IconButton icon="menu" label={ko.menu} open={menu} onPress={onMenu} />
      </View>
      <Row icon="flag" tone={colors.gold.fg} label={ko.row.goal}>
        <Item color={colors.fg.default}>{view.chapter.aim}</Item>
      </Row>
      {hero && onHero ? <HeroSheet player={view.player} journal={view.journal} onGrowth={onGrowth} onClose={onHero} /> : null}
    </View>
  );
}
