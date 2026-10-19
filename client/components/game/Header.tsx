import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { MenuIcon } from './Menu';
import { Item, Row } from './Row';
import { HeroIcon, HeroSheet } from './Self';

export function Header({ view, menu, onMenu, hero, onHero, onGrowth }: {
  view: GameView; menu: boolean; onMenu?: () => void; hero: boolean; onHero?: () => void; onGrowth?: () => void;
}) {
  return (
    <View className="z-20 pt-1">
      <View className="flex-row items-center pl-4 pr-2">
        <Text numberOfLines={1} className="min-w-0 flex-1 pr-2 font-sans-semibold text-panel text-fg-default">
          {ko.chapterNo(view.chapter.k)} {view.chapter.title}
        </Text>
        <HeroIcon player={view.player} open={hero} growth={!!onGrowth} onPress={onHero} />
        <MenuIcon open={menu} onPress={onMenu} />
      </View>
      <Row label={ko.row.goal}><Item tone="gold">{view.chapter.aim}</Item></Row>
      {hero && onHero ? <HeroSheet player={view.player} journal={view.journal} onGrowth={onGrowth} onClose={onHero} /> : null}
    </View>
  );
}
