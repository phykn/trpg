import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Face } from '@/components/game/Dice';
import { ko } from '@/locale/ko';
import type { GameView, Story } from '@/services/types';

function Language() {
  return (
    <View className="flex-row self-end rounded-md border border-border-default">
      <View accessibilityRole="radio" accessibilityState={{ selected: true }} className="rounded-md bg-accent-muted px-2 py-0.5">
        <Text className="font-sans-semibold text-chip text-gold-fg">{ko.korean}</Text>
      </View>
      <View accessibilityRole="radio" accessibilityState={{ selected: false, disabled: true }} className="px-2 py-0.5 opacity-40">
        <Text className="font-sans text-chip text-fg-muted">English</Text>
      </View>
    </View>
  );
}

function Resume({ view, onPress }: { view: GameView; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress}
      className="flex-row items-center rounded-lg border border-gold-fg bg-accent-muted px-4 py-3">
      <View className="min-w-0 flex-1">
        <Text className="font-sans-semibold text-chip text-gold-fg">{ko.resume}</Text>
        <Text className="font-serif text-title text-fg-default">{view.story.title}</Text>
        <Text className="font-sans text-chip text-fg-muted">{ko.chapter(view.chapter.k, view.chapter.title)} · {view.scene.place.name}</Text>
      </View>
      <Text className="font-sans text-title text-gold-fg">›</Text>
    </Pressable>
  );
}

function Shelf({ stories, onPick, primary }: { stories: Story[]; onPick: (id: string) => void; primary: boolean }) {
  const [at, setAt] = useState(0);
  const s = stories[Math.min(at, stories.length - 1)];
  if (!s) return null;
  const many = stories.length > 1;
  const step = (d: number) => setAt((at + d + stories.length) % stories.length);
  return (
    <View className="gap-2">
      <View className="gap-2 rounded-lg border border-border-default bg-canvas-subtle px-4 py-3">
        <View className="flex-row items-center">
          {many ? <Nav glyph="‹" label={ko.prev} onPress={() => step(-1)} /> : null}
          <Text accessibilityRole="header" className="flex-1 text-center font-serif text-title text-fg-default">{s.title}</Text>
          {many ? <Nav glyph="›" label={ko.next} onPress={() => step(1)} /> : null}
        </View>
        <Text className="min-h-[60px] font-sans text-panel text-fg-muted">{s.premise}</Text>
        {many ? (
          <View className="flex-row justify-center gap-1.5">
            {stories.map((x, i) => <View key={x.id} className={`h-1.5 w-1.5 rounded-full ${i === at ? 'bg-gold-fg' : 'bg-border-strong'}`} />)}
          </View>
        ) : null}
      </View>
      <Pressable accessibilityRole="button" onPress={() => onPick(s.id)}
        className={`items-center rounded-md py-3 ${primary ? 'bg-gold-fg' : 'border border-border-strong'}`}>
        <Text className={`font-sans-semibold text-body ${primary ? 'text-fg-on-emphasis' : 'text-fg-default'}`}>{ko.begin}</Text>
      </Pressable>
    </View>
  );
}

function Nav({ glyph, label, onPress }: { glyph: string; label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} className="px-2">
      <Text className="font-sans text-title text-fg-muted">{glyph}</Text>
    </Pressable>
  );
}

export function Title({ stories, saved, onResume, onPick }: {
  stories: Story[]; saved: GameView | null; onResume: () => void; onPick: (id: string) => void;
}) {
  return (
    <View className="min-h-0 flex-1 gap-3 px-5 pb-5 pt-3">
      <Language />
      <View className="min-h-0 flex-1 items-center justify-center gap-4">
        <View className="flex-row gap-3">
          <View style={{ transform: [{ rotate: '-14deg' }] }}><Face value={5} /></View>
          <View style={{ transform: [{ rotate: '9deg' }, { translateY: 6 }] }}><Face value={2} /></View>
        </View>
        <Text accessibilityRole="header" className="font-serif text-display tracking-[2px] text-fg-default">{ko.brand}</Text>
        <View className="h-[1px] w-10 bg-gold-fg" />
        <Text className="font-sans text-panel tracking-[1px] text-fg-muted">{ko.tagline}</Text>
      </View>
      {saved ? <Resume view={saved} onPress={onResume} /> : null}
      <Shelf stories={stories} onPick={onPick} primary={!saved} />
    </View>
  );
}
