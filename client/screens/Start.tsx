import { useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';

import { Notice, Resend } from '@/components/game/CommandBar';
import { Button, IconButton, pressed } from '@/components/ui/Button';
import { Icon, type IconName } from '@/components/ui/Icon';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Creation, GameView, Story } from '@/services/types';
import { Title } from './Title';

function zero(story: Story): Record<string, number> {
  return Object.fromEntries(story.approach_names.map((a) => [a.id, 0]));
}

// What is left to choose shows as empty dots, so the section says how far along it is without a count.
function Section({ icon, label, used, of }: { icon: IconName; label: string; used: number; of: number }) {
  return (
    <View accessibilityLabel={`${label} ${used}/${of}`} className="h-5 flex-row items-center gap-2 px-1">
      <Icon name={icon} size={14} color={colors.gold.fg} />
      <Text className="min-w-0 flex-1 font-sans-semibold text-chip text-fg-muted">{label}</Text>
      <View className="flex-row gap-1">
        {Array.from({ length: of }, (_, i) => (
          <View key={i} className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: i < used ? colors.gold.fg : 'transparent', borderWidth: 1, borderColor: i < used ? colors.gold.fg : colors.border.strong }} />
        ))}
      </View>
    </View>
  );
}

// `again` opens creation for that story at once: starting over from an ending skips the title.
// A lost answer to creating puts the resend where the start button was (`onResend`), as a command's does in the input bar.
export function Start({ stories, busy, saved, again, notice, onCreate, onResume, onResend }: {
  stories: Story[]; busy: boolean; saved: GameView | null; again: string | null; notice: string | null;
  onCreate: (story: string, c: Creation) => void; onResume: () => void; onResend?: () => void;
}) {
  const [id, setId] = useState<string | null>(again);
  const story = stories.find((s) => s.id === id);
  const [placed, setPlaced] = useState<Record<string, number>>(() => (story ? zero(story) : {}));
  const [traits, setTraits] = useState<string[]>([]);
  const [name, setName] = useState('');
  const [focus, setFocus] = useState(false);
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
    <View className="min-h-0 flex-1 gap-2.5 px-4 pb-3 pt-2">
      <View className="h-11 flex-row items-center gap-2">
        <IconButton icon="back" label={ko.back} tone="outline" onPress={() => setId(null)} />
        <View className={`h-11 min-w-0 flex-1 flex-row items-center gap-2 rounded-full border bg-canvas-subtle px-4 ${focus ? 'border-gold-fg' : 'border-border-default'}`}>
          <Icon name="user" size={15} color={focus ? colors.gold.fg : colors.fg.subtle} />
          <TextInput accessibilityLabel={ko.name} value={name} onChangeText={setName} maxLength={10}
            onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
            placeholder={ko.hero} placeholderTextColor={colors.fg.subtle}
            className="h-full min-w-0 flex-1 font-sans text-body text-fg-default" style={{ outlineStyle: 'none' } as object} />
        </View>
      </View>
      <View className="gap-1">
        <Section icon="bolt" label={ko.approaches} used={spent} of={total} />
        {story.approach_names.map((a) => (
          <View key={a.id} className="h-10 flex-row items-center gap-2 rounded-xl bg-canvas-subtle pl-3 pr-1">
            <Text className="w-[44px] font-sans-semibold text-panel text-fg-default">{a.name}</Text>
            <Text numberOfLines={1} className="min-w-0 flex-1 font-sans text-chip text-fg-muted">{a.hint}</Text>
            <IconButton icon="minus" size={30} label={`${a.name} ${ko.lower}`} onPress={placed[a.id] > 0 ? () => add(a.id, -1) : undefined} />
            <Text className="w-4 text-center font-mono-medium text-body text-gold-fg">{placed[a.id]}</Text>
            <IconButton icon="plus" size={30} label={`${a.name} ${ko.raise}`}
              onPress={placed[a.id] < cap && spent < total ? () => add(a.id, 1) : undefined} />
          </View>
        ))}
      </View>
      <View className="gap-1">
        <Section icon="star" label={ko.traits} used={traits.length} of={story.pick} />
        {story.traits.map((t) => {
          const on = traits.includes(t.id);
          return (
            <Pressable key={t.id} accessibilityRole="checkbox" accessibilityLabel={`${t.name}, ${t.text}`}
              accessibilityState={{ checked: on }} onPress={() => toggle(t.id)}
              style={pressed}
              className={`h-10 flex-row items-center gap-2 rounded-xl px-3 ${on ? 'bg-gold-muted' : 'bg-canvas-subtle'}`}>
              <Text className="w-[44px] font-sans-semibold text-panel text-fg-default">{t.name}</Text>
              <Text numberOfLines={1} className="min-w-0 flex-1 font-sans text-chip text-fg-muted">{t.text}</Text>
              <View className="h-5 w-5 items-center justify-center rounded-[6px]"
                style={{ borderWidth: 1.5, borderColor: on ? colors.gold.fg : colors.border.strong, backgroundColor: on ? colors.gold.fg : 'transparent' }}>
                {on ? <Icon name="check" size={12} color={colors.fg['on-emphasis']} width={3} /> : null}
              </View>
            </Pressable>
          );
        })}
      </View>
      <View className="mt-auto gap-1.5">
        {notice ? <Notice text={notice} /> : null}
        {onResend ? <Resend onResend={onResend} /> : (
          <Button icon="play" label={ko.create} disabled={!ready}
            onPress={() => onCreate(story.id, { name: name.trim() || ko.hero, approaches: placed, traits })} />
        )}
      </View>
    </View>
  );
}
