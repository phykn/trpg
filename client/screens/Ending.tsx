import { ScrollView, Text, View } from 'react-native';

import { Speaker, Spoken } from '@/components/game/ChatLog';
import { QUESTIONS } from '@/components/game/ConcludeSheet';
import { Button } from '@/components/ui/Button';
import { Resend } from '@/components/ui/Resend';
import { surface, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { Entry, Phase } from '@/logic/useGame';
import type { Answer, GameView } from '@/services/types';

const TONE: Record<Answer, string> = { hit: 'text-health-fg', miss: 'text-danger-fg', blank: 'text-fg-muted' };

// The verdict, the accused's answer and the ending told in the last turn's text, then the answers and what was left closed once it is told.
export function Ending({ view, log, phase, onRetryText, onLeave }: {
  view: GameView; log: Entry[]; phase: Phase; onRetryText: () => void; onLeave: () => void;
}) {
  const ending = view.ending!;
  const texts = log.filter((e): e is Extract<Entry, { slot: number }> => e.turn === ending.turn && 'slot' in e && !!e.text);
  const busy = phase === 'sending' || phase === 'streaming';
  const met = view.notebook.people.map((l) => l.text);
  return (
    <View className={surface({ kind: 'screen' })}>
      <Text accessibilityRole="header" className={text({ kind: 'hero' })}>{ko.verdicts[ending.verdict]}</Text>
      <ScrollView className="min-h-0 flex-1" contentContainerClassName="gap-5">
        {texts.map((e) => (e.who ? (
          <Speaker key={e.key} who={e.who} met={met}><Spoken text={e.text} className={text()} /></Speaker>
        ) : <Text key={e.key} className={text({ kind: 'scene' })}>{e.text}</Text>))}
        {busy || phase === 'text_error' ? null : (
          <>
            <View className="gap-1.5">
              {QUESTIONS.map((q) => (
                <View key={q} className={surface({ kind: 'card' }, 'flex-row items-center justify-between')}>
                  <Text className={text({ kind: 'strong' })}>{ko.questions[q]}</Text>
                  <Text className={text({ kind: 'strong' }, TONE[ending.answers[q]])}>{ko.answers[ending.answers[q]]}</Text>
                </View>
              ))}
            </View>
            {(['lies', 'held', 'locks'] as const).filter((k) => ending.missed[k].length).map((k) => (
              <View key={k} className="gap-1.5">
                <Text className={text({ kind: 'head' })}>{ko.missed[k]}</Text>
                {ending.missed[k].map((t) => <Text key={t} className={text({ kind: 'panel' })}>{t}</Text>)}
              </View>
            ))}
          </>
        )}
      </ScrollView>
      {phase === 'text_error' ? <Resend onResend={onRetryText} /> : <Button label={ko.toTitle} disabled={busy} onPress={onLeave} />}
    </View>
  );
}
