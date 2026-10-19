import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { MenuIcon } from './Menu';

export function Header({ view, menu, onMenu }: { view: GameView; menu: boolean; onMenu?: () => void }) {
  return (
    <View className="flex-row items-center gap-2 py-1 pl-4 pr-2">
      <Text className="w-[40px] font-sans-semibold text-chip text-fg-default">{ko.chapterNo(view.chapter.k)}</Text>
      <Text className="min-w-0 flex-1 font-sans text-chip text-gold-fg">{view.chapter.aim}</Text>
      <MenuIcon open={menu} onPress={onMenu} />
    </View>
  );
}
