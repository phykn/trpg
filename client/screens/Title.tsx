import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Face } from '@/components/game/Dice';
import { ko } from '@/locale/ko';
import type { GameView, Story } from '@/services/types';
import { version } from '../package.json';

function Language() {
  return (
    <View className="flex-row gap-3 self-end">
      <Text accessibilityRole="radio" accessibilityState={{ selected: true }} className="font-sans-semibold text-chip text-fg-default">{ko.korean}</Text>
      <Text accessibilityRole="radio" accessibilityState={{ selected: false, disabled: true }} className="font-sans text-chip text-fg-subtle opacity-50">English</Text>
    </View>
  );
}

function Shelf({ stories, at, onStep }: { stories: Story[]; at: number; onStep: (d: number) => void }) {
  const s = stories[at];
  const many = stories.length > 1;
  return (
    <View className="gap-1 rounded-lg border border-border-default bg-canvas-subtle px-4 py-3">
      <View className="flex-row items-center">
        <Text accessibilityRole="header" className="min-w-0 flex-1 font-serif text-title text-fg-default">{s.title}</Text>
        {many ? <Nav glyph="‹" label={ko.prev} onPress={() => onStep(-1)} /> : null}
        {many ? <Nav glyph="›" label={ko.next} onPress={() => onStep(1)} /> : null}
      </View>
      <Text className="font-sans text-panel text-fg-muted">{s.premise}</Text>
    </View>
  );
}

function Action({ label, sub, primary, onPress }: { label: string; sub?: string; primary: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress}
      className={`flex-row items-center justify-center gap-2 rounded-md py-3 ${primary ? 'bg-gold-fg' : 'border border-border-strong'}`}>
      <Text className={`font-sans-semibold text-body ${primary ? 'text-fg-on-emphasis' : 'text-fg-default'}`}>{label}</Text>
      {sub ? <Text className={`font-sans text-panel ${primary ? 'text-fg-on-emphasis opacity-70' : 'text-fg-muted'}`}>{sub}</Text> : null}
    </Pressable>
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
  const [at, setAt] = useState(() => Math.max(0, stories.findIndex((x) => x.id === saved?.story.id)));
  const s = stories[Math.min(at, stories.length - 1)];
  const here = saved && s && saved.story.id === s.id ? saved : null;
  return (
    <View className="min-h-0 flex-1 gap-3 px-5 pb-3 pt-3">
      <Language />
      <View className="min-h-0 flex-1 items-center justify-center gap-4">
        <View className="flex-row gap-3">
          <View style={{ transform: [{ rotate: '-14deg' }] }}><Face value={5} /></View>
          <View style={{ transform: [{ rotate: '9deg' }, { translateY: 6 }] }}><Face value={2} /></View>
        </View>
        <Text accessibilityRole="header" className="font-serif text-display tracking-[2px] text-fg-default">{ko.brand}</Text>
        <View className="h-[1px] w-10 bg-gold-fg" />
      </View>
      {s ? (
        <>
          <Shelf stories={stories} at={stories.indexOf(s)} onStep={(d) => setAt((stories.indexOf(s) + d + stories.length) % stories.length)} />
          <View className="gap-2">
            {here ? <Action primary label={ko.resume} sub={[here.player.name, ko.chapterNo(here.chapter.k), here.scene.place.name].filter(Boolean).join(' · ')} onPress={onResume} /> : null}
            <Action primary={!here} label={ko.begin} onPress={() => onPick(s.id)} />
          </View>
        </>
      ) : null}
      <Text className="text-center font-sans text-caption text-fg-subtle">v{version} · © 2026 All rights reserved.</Text>
    </View>
  );
}
