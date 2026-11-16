import { ScrollView, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Choice, Sheet } from '@/components/ui/Sheet';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { findLine } from '@/logic/notebook';

export type Question = 'who' | 'how' | 'why';
export type Picks = Record<Question, number | null>;
export const QUESTIONS: Question[] = ['who', 'how', 'why'];

const lineText = (view: GameView, id: number | null) => (id === null ? undefined : findLine(view, id)?.line.text);

// Without onMore (the cells are spent) the sheet cannot be closed; only the notebook can be read.
export function ConcludeSheet({ view, picks, locked, onPick, onSubmit, onMore, onNotebook }: {
  view: GameView; picks: Picks; locked: boolean; onPick: (q: Question) => void; onSubmit: () => void; onMore?: () => void;
  onNotebook: () => void;
}) {
  return (
    <Sheet title={ko.conclusion} icon="flag" onClose={onMore}>
      <View className="gap-2">
        {QUESTIONS.map((q) => <Choice key={q} label={ko.questions[q]} sub={lineText(view, picks[q])} onPress={() => onPick(q)} />)}
      </View>
      <View className="gap-2">
        <Button label={ko.submit} disabled={locked} onPress={onSubmit} />
        {onMore ? <Button tone="secondary" label={ko.more} onPress={onMore} />
          : <Button tone="secondary" icon="book" label={ko.notebook} onPress={onNotebook} />}
      </View>
    </Sheet>
  );
}

export function PickSheet({ view, question, chosen, onPick, onClose }: {
  view: GameView; question: Question; chosen: number | null; onPick: (id: number | null) => void; onClose: () => void;
}) {
  const ids = question === 'who' ? view.conclude?.who ?? [] : view.conclude?.clues ?? [];
  return (
    <Sheet full title={ko.questions[question]} onClose={onClose}>
      <ScrollView className="min-h-0 flex-1" contentContainerClassName="gap-2">
        <Choice label={ko.blank} primary={chosen === null} onPress={() => onPick(null)} />
        {ids.map((id) => <Choice key={id} label={lineText(view, id) ?? ''} primary={chosen === id} onPress={() => onPick(id)} />)}
      </ScrollView>
    </Sheet>
  );
}
