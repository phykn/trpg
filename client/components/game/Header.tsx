import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

export function Header({ view }: { view: GameView }) {
  return (
    <View className="flex-row items-center px-4 py-1">
      <Text numberOfLines={1} className="font-sans-semibold text-panel text-fg-default">
        {ko.chapter(view.chapter.k, view.chapter.title)}
        <Text className="text-fg-muted"> · {view.scene.place.name}</Text>
      </Text>
    </View>
  );
}
