import { ScrollView, Text, View } from 'react-native';

import { QUESTIONS } from '@/components/game/ConcludeSheet';
import { Button } from '@/components/ui/Button';
import { Resend } from '@/components/ui/Resend';
import { ko } from '@/locale/ko';
import type { Entry, Phase } from '@/logic/useGame';
import type { Answer, GameView } from '@/services/types';

const TONE: Record<Answer, string> = { hit: 'text-health-fg', miss: 'text-danger-fg', blank: 'text-fg-muted' };

export function Ending({ view, log, phase, onRetryText, onLeave }: {
  view: GameView; log: Entry[]; phase: Phase; onRetryText: () => void; onLeave: () => void;
}) {
  const ending = view.ending!;
  const texts = log.filter((e) => e.turn === ending.turn && 'slot' in e && !!e.text);
  const busy = phase === 'sending' || phase === 'streaming';
  return (
    <View className="min-h-0 flex-1 gap-4 px-4 py-6">
      <Text accessibilityRole="header" className="font-serif text-hero text-fg-default">{ko.verdicts[ending.verdict]}</Text>
      <ScrollView className="min-h-0 flex-1" contentContainerClassName="gap-5">
        {texts.map((e) => <Text key={e.key} className="font-serif-body text-body text-fg-default">{e.text}</Text>)}
        {busy || phase === 'text_error' ? null : (
          <>
            <View className="gap-1.5">
              {QUESTIONS.map((q) => (
                <View key={q} className="flex-row items-center justify-between rounded-xl border border-border-default px-4 py-2.5">
                  <Text className="font-sans-semibold text-body text-fg-default">{ko.questions[q]}</Text>
                  <Text className={`font-sans-semibold text-body ${TONE[ending.answers[q]]}`}>{ko.answers[ending.answers[q]]}</Text>
                </View>
              ))}
            </View>
            {(['lies', 'held', 'locks'] as const).map((k) => (ending.missed[k].length ? (
              <View key={k} className="gap-1.5">
                <Text className="font-sans-semibold text-chip text-fg-muted">{ko.missed[k]}</Text>
                {ending.missed[k].map((t) => <Text key={t} className="font-sans text-panel text-fg-default">{t}</Text>)}
              </View>
            ) : null))}
          </>
        )}
      </ScrollView>
      {phase === 'text_error' ? <Resend onResend={onRetryText} /> : <Button label={ko.toTitle} disabled={busy} onPress={onLeave} />}
    </View>
  );
}
