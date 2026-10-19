import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { MenuIcon } from './Menu';
import { HeroIcon, HeroSheet } from './Self';

export function Header({ view, menu, onMenu, hero, onHero, onGrowth }: {
  view: GameView; menu: boolean; onMenu?: () => void; hero: boolean; onHero?: () => void; onGrowth?: () => void;
}) {
  return (
    <View className="z-20 flex-row items-start py-1 pl-4 pr-2">
      <Text className="w-[52px] font-sans-semibold text-chip text-fg-default">{ko.chapterNo(view.chapter.k)}</Text>
      <Text className="min-w-0 flex-1 pr-2 font-sans text-chip text-gold-fg">{view.chapter.aim}</Text>
      <HeroIcon player={view.player} open={hero} growth={!!onGrowth} onPress={onHero} />
      <MenuIcon open={menu} onPress={onMenu} />
      {hero && onHero ? <HeroSheet player={view.player} journal={view.journal} onGrowth={onGrowth} onClose={onHero} /> : null}
    </View>
  );
}
