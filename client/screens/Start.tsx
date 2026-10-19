import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { Creation, GameView, Story } from '@/services/types';
import { Title } from './Title';

function initial(story: Story): Record<string, number> {
  const values = [...story.approaches].sort((a, b) => b - a);
  return Object.fromEntries(story.approach_names.map((a, i) => [a.id, values[i]]));
}

// Values only trade places, so the spread always stays the story's (ontology.md 5).
function swapTarget(placed: Record<string, number>, id: string, dir: 1 | -1): string | null {
  const v = placed[id];
  const others = Object.entries(placed).filter(([k, x]) => k !== id && (dir > 0 ? x > v : x < v));
  if (!others.length) return null;
  const best = dir > 0 ? Math.min(...others.map(([, x]) => x)) : Math.max(...others.map(([, x]) => x));
  return others.find(([, x]) => x === best)![0];
}

function swap(placed: Record<string, number>, a: string, b: string): Record<string, number> {
  return { ...placed, [a]: placed[b], [b]: placed[a] };
}

function Arrow({ label, glyph, onPress }: { label: string; glyph: string; onPress?: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !onPress }}
      disabled={!onPress} onPress={onPress} className={`px-1 py-1 ${onPress ? '' : 'opacity-20'}`}>
      <Text className="font-sans text-chip text-fg-muted">{glyph}</Text>
    </Pressable>
  );
}

export function Start({ stories, busy, saved, onCreate, onResume }: {
  stories: Story[]; busy: boolean; saved: GameView | null; onCreate: (story: string, c: Creation) => void; onResume: () => void;
}) {
  const [id, setId] = useState<string | null>(null);
  const story = stories.find((s) => s.id === id);
  const [placed, setPlaced] = useState<Record<string, number>>({});
  const [traits, setTraits] = useState<string[]>([]);
  const pick = (s: string) => {
    const next = stories.find((x) => x.id === s);
    setId(s); setPlaced(next ? initial(next) : {}); setTraits([]);
  };
  if (!story) return <Title stories={stories} saved={saved} onResume={onResume} onPick={pick} />;

  const toggle = (t: string) => setTraits(traits.includes(t) ? traits.filter((x) => x !== t)
    : traits.length < story.pick ? [...traits, t] : traits);
  const ready = traits.length === story.pick && !busy;

  return (
    <View className="min-h-0 flex-1 gap-2 px-4 py-3">
      <View className="flex-row flex-wrap items-center gap-2">
        <Pressable accessibilityRole="button" accessibilityLabel={ko.back} onPress={() => setId(null)} className="px-1 py-1">
          <Text className="font-sans-semibold text-title text-fg-muted">‹</Text>
        </Pressable>
        <Text accessibilityRole="header" className="font-serif text-title text-fg-default">{story.title}</Text>
      </View>
      <Text className="font-sans text-panel text-fg-default">{story.premise}</Text>
      <Text className="font-sans text-chip text-fg-muted">{ko.approaches}</Text>
      <View className="flex-row flex-wrap gap-2">
        {story.approach_names.map((a) => {
          const up = swapTarget(placed, a.id, 1);
          const down = swapTarget(placed, a.id, -1);
          return (
            <View key={a.id} className="w-[47%] rounded-md border border-border-default px-3 py-1">
              <View className="flex-row items-center justify-between">
                <Text className="font-sans-semibold text-panel text-fg-default">{a.name}</Text>
                <View className="flex-row items-center">
                  <Arrow label={`${a.name} ${ko.lower}`} glyph="◀" onPress={down ? () => setPlaced(swap(placed, a.id, down)) : undefined} />
                  <Text className="w-[20px] text-center font-mono-medium text-body text-gold-fg">{placed[a.id]}</Text>
                  <Arrow label={`${a.name} ${ko.raise}`} glyph="▶" onPress={up ? () => setPlaced(swap(placed, a.id, up)) : undefined} />
                </View>
              </View>
              <Text className="font-sans text-chip text-fg-muted">{a.hint}</Text>
            </View>
          );
        })}
      </View>
      <Text className="font-sans text-chip text-fg-muted">{ko.pickTraits(traits.length, story.pick)}</Text>
      <View className="flex-row flex-wrap gap-2">
        {story.traits.map((t) => (
          <Pressable key={t.id} accessibilityRole="checkbox" accessibilityState={{ checked: traits.includes(t.id) }}
            onPress={() => toggle(t.id)}
            className={`w-[47%] rounded-md border px-3 py-1 ${traits.includes(t.id) ? 'border-gold-fg bg-accent-muted' : 'border-border-default'}`}>
            <Text className="font-sans-semibold text-panel text-fg-default">{t.name}</Text>
            <Text className="font-sans text-chip text-fg-muted">{t.text}</Text>
          </Pressable>
        ))}
      </View>
      <Pressable accessibilityRole="button" accessibilityState={{ disabled: !ready }} disabled={!ready}
        onPress={() => onCreate(story.id, { approaches: placed, traits })}
        className={`mt-auto items-center rounded-md bg-gold-fg py-3 ${ready ? '' : 'opacity-40'}`}>
        <Text className="font-sans-semibold text-body text-fg-on-emphasis">{ko.create}</Text>
      </Pressable>
    </View>
  );
}
