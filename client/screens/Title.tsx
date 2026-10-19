import { useState } from 'react';
import { Text, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { Face } from '@/components/game/Dice';
import { Button, IconButton } from '@/components/ui/Button';
import { useEnter } from '@/components/ui/motion';
import { ko } from '@/locale/ko';
import type { GameView, Story } from '@/services/types';
import { version } from '../package.json';

function Shelf({ stories, at, onStep }: { stories: Story[]; at: number; onStep: (d: number) => void }) {
  const s = stories[at];
  const many = stories.length > 1;
  return (
    <View className="gap-1.5 rounded-2xl border border-border-default bg-canvas-subtle px-4 py-3.5">
      <View className="min-h-[36px] flex-row items-center">
        {many ? <IconButton icon="back" label={ko.prev} onPress={() => onStep(-1)} /> : null}
        <Text accessibilityRole="header" className={`min-w-0 flex-1 font-serif text-title text-fg-default ${many ? 'text-center' : ''}`}>{s.title}</Text>
        {many ? <IconButton icon="next" label={ko.next} onPress={() => onStep(1)} /> : null}
      </View>
      <Text className="font-sans text-panel text-fg-muted">{s.premise}</Text>
    </View>
  );
}

export function Title({ stories, saved, onResume, onPick }: {
  stories: Story[]; saved: GameView | null; onResume: () => void; onPick: (id: string) => void;
}) {
  const [at, setAt] = useState(() => Math.max(0, stories.findIndex((x) => x.id === saved?.story.id)));
  const s = stories[Math.min(at, stories.length - 1)];
  const here = saved && s && saved.story.id === s.id ? saved : null;
  const logo = useEnter(10);
  const shelf = useEnter(12, 120);
  return (
    <View className="min-h-0 flex-1 gap-3 px-4 pb-3 pt-3">
      <Animated.View style={[{ flex: 1, minHeight: 0 }, logo]}>
        <View className="min-h-0 flex-1 items-center justify-center gap-4">
          <View className="flex-row gap-3">
            <View style={{ transform: [{ rotate: '-14deg' }] }}><Face value={5} /></View>
            <View style={{ transform: [{ rotate: '9deg' }, { translateY: 6 }] }}><Face value={2} /></View>
          </View>
          <Text accessibilityRole="header" className="font-serif text-display tracking-[2px] text-fg-default">{ko.brand}</Text>
          <View className="h-[1px] w-10 bg-gold-fg" />
        </View>
      </Animated.View>
      {s ? (
        <Animated.View style={shelf}>
          <View className="gap-3">
            <Shelf stories={stories} at={stories.indexOf(s)} onStep={(d) => setAt((stories.indexOf(s) + d + stories.length) % stories.length)} />
            <View className="gap-2">
              {here ? (
                <Button icon="play" label={ko.resume} onPress={onResume}
                  sub={[here.player.name, ko.chapterNo(here.chapter.k), here.scene.place.name].filter(Boolean).join(' · ')} />
              ) : null}
              <Button tone={here ? 'secondary' : 'primary'} icon="plus" label={ko.begin} onPress={() => onPick(s.id)} />
            </View>
          </View>
        </Animated.View>
      ) : null}
      <Text className="text-center font-sans text-caption text-fg-subtle">v{version}</Text>
    </View>
  );
}
