import { useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Creation, GameView, Story } from '@/services/types';
import { Title } from './Title';

function zero(story: Story): Record<string, number> {
  return Object.fromEntries(story.approach_names.map((a) => [a.id, 0]));
}

function Arrow({ label, glyph, onPress }: { label: string; glyph: string; onPress?: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !onPress }}
      disabled={!onPress} onPress={onPress} className={`px-1.5 py-1 ${onPress ? '' : 'opacity-20'}`}>
      <Text className="font-sans text-panel text-fg-muted">{glyph}</Text>
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
  const [name, setName] = useState('');
  const pick = (s: string) => {
    const next = stories.find((x) => x.id === s);
    setId(s); setPlaced(next ? zero(next) : {}); setTraits([]);
  };
  if (!story) return <Title stories={stories} saved={saved} onResume={onResume} onPick={pick} />;

  const toggle = (t: string) => setTraits(traits.includes(t) ? traits.filter((x) => x !== t)
    : traits.length < story.pick ? [...traits, t] : traits);
  const total = story.approaches.reduce((a, b) => a + b, 0);
  const cap = Math.max(...story.approaches);
  const spent = Object.values(placed).reduce((a, b) => a + b, 0);
  const add = (ap: string, d: number) => setPlaced({ ...placed, [ap]: placed[ap] + d });
  const ready = spent === total && traits.length === story.pick && !busy;

  return (
    <View className="min-h-0 flex-1 gap-3 px-5 pb-4 pt-2">
      <View className="flex-row items-center gap-3">
        <Pressable accessibilityRole="button" accessibilityLabel={ko.back} onPress={() => setId(null)}
          className="h-[32px] w-[32px] items-center justify-center rounded-full border border-border-default">
          <View style={{ width: 8, height: 8, marginLeft: 3, borderLeftWidth: 1.5, borderBottomWidth: 1.5, transform: [{ rotate: '45deg' }] }}
            className="border-fg-muted" />
        </Pressable>
        <Text accessibilityRole="header" className="min-w-0 flex-1 font-serif text-title text-fg-default">{story.title}</Text>
      </View>
      <View className="gap-1.5">
        <Text className="font-sans-semibold text-chip text-gold-fg">{ko.name}</Text>
        <TextInput accessibilityLabel={ko.name} value={name} onChangeText={setName} maxLength={10}
          placeholder={ko.hero} placeholderTextColor={colors.fg.subtle}
          className="h-[44px] rounded-md border border-border-default px-4 font-sans text-body text-fg-default" />
      </View>
      <View className="gap-1.5">
        <Text className="font-sans-semibold text-chip text-gold-fg">{ko.count(ko.approaches, spent, total)}</Text>
        <View className="gap-1">
          {story.approach_names.map((a) => (
            <View key={a.id} className="h-[44px] flex-row items-center gap-2 rounded-md border border-border-default px-4">
              <Text className="w-[52px] font-sans-semibold text-body text-fg-default">{a.name}</Text>
              <Text className="min-w-0 flex-1 font-sans text-panel text-fg-muted">{a.hint}</Text>
              <View className="flex-row items-center gap-1">
                <Arrow label={`${a.name} ${ko.lower}`} glyph="◀" onPress={placed[a.id] > 0 ? () => add(a.id, -1) : undefined} />
                <Text className="w-[24px] text-center font-mono-medium text-body text-gold-fg">{placed[a.id]}</Text>
                <Arrow label={`${a.name} ${ko.raise}`} glyph="▶"
                  onPress={placed[a.id] < cap && spent < total ? () => add(a.id, 1) : undefined} />
              </View>
            </View>
          ))}
        </View>
      </View>
      <View className="gap-1.5">
        <Text className="font-sans-semibold text-chip text-gold-fg">{ko.count(ko.traits, traits.length, story.pick)}</Text>
        <View className="gap-1">
          {story.traits.map((t) => (
            <Pressable key={t.id} accessibilityRole="checkbox" accessibilityState={{ checked: traits.includes(t.id) }}
              onPress={() => toggle(t.id)}
              className={`h-[44px] flex-row items-center gap-2 rounded-md border px-4 ${traits.includes(t.id) ? 'border-gold-fg bg-accent-muted' : 'border-border-default'}`}>
              <Text className="w-[52px] font-sans-semibold text-body text-fg-default">{t.name}</Text>
              <Text className="min-w-0 flex-1 font-sans text-panel text-fg-muted">{t.text}</Text>
            </Pressable>
          ))}
        </View>
      </View>
      <Pressable accessibilityRole="button" accessibilityState={{ disabled: !ready }} disabled={!ready}
        onPress={() => onCreate(story.id, { name: name.trim() || ko.hero, approaches: placed, traits })}
        className={`mt-auto items-center rounded-md bg-gold-fg py-3 ${ready ? '' : 'opacity-40'}`}>
        <Text className="font-sans-semibold text-body text-fg-on-emphasis">{ko.create}</Text>
      </Pressable>
    </View>
  );
}
