import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { MenuIcon } from './Menu';

export function Header({ view, menu, onMenu }: { view: GameView; menu: boolean; onMenu?: () => void }) {
  return (
    <View className="flex-row items-center gap-2 py-1 pl-4 pr-2">
      <Text numberOfLines={1} className="min-w-0 flex-1 font-sans-semibold text-panel text-fg-default">
        {ko.chapter(view.chapter.k, view.chapter.title)}
        <Text className="text-fg-muted"> · {view.scene.place.name}</Text>
      </Text>
      <MenuIcon open={menu} onPress={onMenu} />
    </View>
  );
}
