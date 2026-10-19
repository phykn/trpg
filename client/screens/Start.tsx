import { useState } from 'react';
import { Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { PagedList } from '@/components/ui/PagedList';
import { Reader } from '@/components/ui/Reader';
import { ko } from '@/locale/ko';
import type { Creation, StoryCard } from '@/services/types';

type Step = 'list' | 'story' | 'mode' | 'strong' | 'weak' | 'traits';

export function Start({ catalog, busy, canResume, onStart, onResume }: {
  catalog: StoryCard[];
  busy: boolean;
  canResume: boolean;
  onStart: (story: string, creation?: Creation) => Promise<void>;
  onResume: () => void;
}) {
  const [step, setStep] = useState<Step>(catalog.length === 1 ? 'story' : 'list');
  const [storyId, setStoryId] = useState(catalog.length === 1 ? catalog[0].id : '');
  const [strong, setStrong] = useState('');
  const [weak, setWeak] = useState('');
  const [traits, setTraits] = useState<string[]>([]);
  const story = catalog.find((s) => s.id === storyId);
  const approaches = story?.creation.approaches ?? [];
  const title = step === 'list' || !story ? ko.stories : story.title;

  function begin(creation?: Creation) {
    if (story) void onStart(story.id, creation);
  }

  function toggle(id: string) {
    const next = traits.includes(id) ? traits.filter((t) => t !== id) : [...traits, id].slice(-2);
    setTraits(next);
  }

  function finish() {
    const values = Object.fromEntries(approaches.map((a) => [a.id, a.id === strong ? 2 : a.id === weak ? 0 : 1]));
    begin({ approaches: values, traits });
  }

  return (
    <View className="flex-1 min-h-0 gap-5 px-6 pb-5 pt-6">
      <View className="flex-row items-center gap-3">
        {step !== 'list' && catalog.length > 1 ? <Button label={ko.back} disabled={busy} onPress={() => setStep('list')} /> : null}
        <Text accessibilityRole="header" className="flex-1 font-sans-semibold text-scene text-fg-default">{title}</Text>
      </View>
      {step === 'list' ? <PagedList entries={catalog.map((s) => ({ id: s.id, label: s.title, meta: s.synopsis }))} disabled={busy}
        onSelect={(id) => { setStoryId(id); setStep('story'); }} /> : null}
      {step === 'story' && story ? <Reader text={story.synopsis + (canResume ? `\n\n${ko.newGameHelp}` : '')} doneLabel={ko.begin} disabled={busy}
        onDone={() => (story.creation.choose ? setStep('mode') : begin())} /> : null}
      {step === 'mode' ? (
        <View className="flex-1 min-h-0 justify-end gap-3">
          <Text className="flex-1 font-sans text-body text-fg-muted">{ko.modeHelp}</Text>
          <Button label={ko.defaults} disabled={busy} onPress={() => begin()} />
          <Button label={ko.customize} primary disabled={busy} onPress={() => setStep('strong')} />
        </View>
      ) : null}
      {step === 'strong' ? (
        <View className="flex-1 min-h-0 gap-3">
          <Text className="font-sans text-body text-gold-fg">{ko.strongest}</Text>
          <PagedList entries={approaches.map((a) => ({ id: a.id, label: a.name, meta: a.text }))} onSelect={(id) => { setStrong(id); setStep('weak'); }} />
        </View>
      ) : null}
      {step === 'weak' ? (
        <View className="flex-1 min-h-0 gap-3">
          <Text className="font-sans text-body text-gold-fg">{ko.weakest}</Text>
          <PagedList entries={approaches.filter((a) => a.id !== strong).map((a) => ({ id: a.id, label: a.name, meta: a.text }))} onSelect={(id) => { setWeak(id); setStep('traits'); }} />
        </View>
      ) : null}
      {step === 'traits' && story ? (
        <View className="flex-1 min-h-0 gap-3">
          <Text className="font-sans text-body text-gold-fg">{ko.pickTraits(traits.length)}</Text>
          <PagedList entries={story.creation.traits.map((t) => ({ id: t.id, label: (traits.includes(t.id) ? '✓ ' : '') + t.name, meta: t.text }))} onSelect={toggle} />
          <Button label={ko.begin} primary disabled={busy || traits.length !== 2} onPress={finish} />
        </View>
      ) : null}
      {canResume && step !== 'traits' ? <Button label={ko.resume} disabled={busy} onPress={onResume} /> : null}
    </View>
  );
}
