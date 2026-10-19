import { ActivityIndicator, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Reader } from '@/components/ui/Reader';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Narration as State } from '@/logic/useGame';
import type { GameView } from '@/services/types';

const TAIL = 700;

// What the player did and what the rules decided. It leads the first page so the outcome is never on a later one.
export function outcome(view: GameView): string {
  if (view.turn === 0) return view.intro;
  const latest = view.journal[view.journal.length - 1];
  if (!latest) return '';
  // A pressed button's label is also the first step's label; show it once.
  const said = latest.input && !latest.lines[0]?.startsWith(latest.input) ? [ko.said(latest.input)] : [];
  return [...said, ...latest.lines.map((line) => `· ${line}`)].join('\n');
}

export function Narration({ view, narration, onRetry }: { view: GameView; narration: State; onRetry: () => void }) {
  const latest = view.journal[view.journal.length - 1];
  const head = outcome(view);
  if (narration.status === 'streaming') {
    return (
      <View className="flex-1 min-h-0 gap-3 overflow-hidden">
        {head ? <Text className="font-sans text-body text-gold-fg">{head}</Text> : null}
        <Text accessibilityLiveRegion="polite" className="reader-text font-sans text-lead text-fg-default">{narration.text.slice(-TAIL)}</Text>
        <View className="flex-row items-center gap-2">
          <ActivityIndicator color={colors.gold.fg} />
          <Text className="font-sans text-caption text-gold-fg">{ko.writing}</Text>
        </View>
      </View>
    );
  }
  if (narration.status === 'error' && narration.turn === view.turn) {
    return (
      <View className="flex-1 min-h-0 gap-4">
        {head ? <Text className="font-sans text-body text-gold-fg">{head}</Text> : null}
        <Text accessibilityRole="alert" className="font-sans text-body text-danger-fg">{ko.narrationFailed}</Text>
        {narration.canRetry ? <Button label={ko.rewrite} onPress={onRetry} /> : null}
      </View>
    );
  }
  const ending = view.ending ? `${ko.endingTitle(view.ending.name)}\n\n${view.ending.text}` : '';
  const story = [latest?.narration ?? '', ending].filter(Boolean).join('\n\n');
  const text = [head, story].filter(Boolean).join('\n\n');
  return <Reader key={`${view.turn}:${text.length}`} text={text} />;
}
