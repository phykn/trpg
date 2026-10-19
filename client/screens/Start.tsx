import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { Creation, Story } from '@/services/types';

/** ui.md 5.5: the stories, the approach values placed by tapping, and the traits, on one screen. */
export function Start({ stories, busy, onCreate }: { stories: Story[]; busy: boolean; onCreate: (story: string, c: Creation) => void }) {
  const [id, setId] = useState(stories[0]?.id ?? '');
  const story = stories.find((s) => s.id === id);
  const [placed, setPlaced] = useState<Record<string, number>>({});
  const [traits, setTraits] = useState<string[]>([]);
  if (!story) return null;

  const values = [...story.approaches].sort((a, b) => b - a);
  const left = values.slice(Object.keys(placed).length);
  const place = (ap: string) => {
    if (ap in placed || !left.length) return;
    setPlaced({ ...placed, [ap]: left[0] });
  };
  const toggle = (t: string) => setTraits(traits.includes(t) ? traits.filter((x) => x !== t)
    : traits.length < story.pick ? [...traits, t] : traits);
  const ready = !left.length && traits.length === story.pick && !busy;
  const choose = (s: string) => { setId(s); setPlaced({}); setTraits([]); };

  return (
    <View className="min-h-0 flex-1 gap-3 px-4 py-3">
      <Text accessibilityRole="header" className="font-sans-semibold text-panel text-fg-muted">{ko.stories}</Text>
      <View className="flex-row flex-wrap gap-2">
        {stories.map((s) => (
          <Pressable key={s.id} accessibilityRole="radio" accessibilityState={{ selected: s.id === id }} onPress={() => choose(s.id)}
            className={`rounded-md border px-3 py-2 ${s.id === id ? 'border-gold-fg bg-accent-muted' : 'border-border-default'}`}>
            <Text className="font-sans-semibold text-body text-fg-default">{s.title}</Text>
          </Pressable>
        ))}
      </View>
      <Text className="font-sans text-body text-fg-default">{story.premise}</Text>
      <Text className="font-sans text-chip text-fg-muted">{ko.placeApproaches}</Text>
      <View className="flex-row flex-wrap gap-2">
        {story.approach_names.map((a) => (
          <Pressable key={a.id} accessibilityRole="button" onPress={() => place(a.id)}
            className={`w-[47%] rounded-md border px-3 py-2 ${a.id in placed ? 'border-gold-fg' : 'border-border-default'}`}>
            <Text className="font-sans-semibold text-body text-fg-default">{a.name} {a.id in placed ? placed[a.id] : '·'}</Text>
            <Text className="font-sans text-chip text-fg-muted">{a.hint}</Text>
          </Pressable>
        ))}
      </View>
      <Pressable accessibilityRole="button" onPress={() => setPlaced({})} className="self-start">
        <Text className="font-sans text-chip text-fg-subtle">{ko.resetApproaches}</Text>
      </Pressable>
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
