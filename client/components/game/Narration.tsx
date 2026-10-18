import { ActivityIndicator, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Reader } from '@/components/ui/Reader';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Narration as State } from '@/logic/useGame';
import type { GameView } from '@/services/types';

const TAIL = 700;

export function Narration({ view, narration, onRetry }: { view: GameView; narration: State; onRetry: () => void }) {
  const latest = view.journal[view.journal.length - 1];
  if (narration.status === 'streaming') {
    return (
      <View className="flex-1 min-h-0 gap-3 overflow-hidden">
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
        <Text accessibilityRole="alert" className="font-sans text-body text-danger-fg">{ko.narrationFailed}</Text>
        {narration.canRetry ? <Button label={ko.rewrite} onPress={onRetry} /> : null}
      </View>
    );
  }
  const story = view.ending ? `${view.ending.name}\n\n${view.ending.text}` : latest?.narration ?? (view.turn === 0 ? view.intro : '');
  const lines = latest?.lines.map((line) => `· ${line}`).join('\n') ?? '';
  const text = [story, lines].filter(Boolean).join('\n\n');
  return <Reader key={`${view.turn}:${text.length}`} text={text} />;
}
