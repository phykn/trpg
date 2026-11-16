import { BottomSheetScrollView } from '@gorhom/bottom-sheet';
import { View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { DragSheet } from '@/components/ui/DragSheet';
import { Choice } from '@/components/ui/Sheet';
import { spacing } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { findLine } from '@/logic/notebook';
import type { GameView } from '@/services/types';

export type Question = 'who' | 'how' | 'why';
export type Picks = Record<Question, number | null>;
export const QUESTIONS: Question[] = ['who', 'how', 'why'];

const showLine = (view: GameView, id: number | null) => (id === null ? undefined : findLine(view, id)?.line.text);

// Without onClose (the turns are spent) the sheet cannot be closed; only the notebook can still be read.
export function ConcludeSheet({ view, picks, locked, onPick, onSubmit, onClose, onNotebook }: {
  view: GameView; picks: Picks; locked: boolean; onPick: (question: Question) => void; onSubmit: () => void;
  onClose?: () => void; onNotebook: () => void;
}) {
  return (
    <DragSheet fit title={ko.conclusion} onClose={onClose}>
      <View className="gap-2">
        {QUESTIONS.map((q) => <Choice key={q} label={ko.questions[q]} sub={showLine(view, picks[q])} onPress={() => onPick(q)} />)}
      </View>
      <View className="gap-2">
        <Button label={ko.submit} disabled={locked} onPress={onSubmit} />
        {onClose ? null : <Button tone="secondary" icon="book" label={ko.notebook} onPress={onNotebook} />}
      </View>
    </DragSheet>
  );
}

// "Who" offers the people in the notebook; "how" and "why" offer what was seen and heard.
export function PickSheet({ view, question, chosen, onPick, onClose }: {
  view: GameView; question: Question; chosen: number | null; onPick: (id: number | null) => void; onClose: () => void;
}) {
  const ids = (question === 'who' ? view.conclude?.who : view.conclude?.clues) ?? [];
  return (
    <DragSheet title={ko.questions[question]} onClose={onClose}>
      <BottomSheetScrollView style={{ flex: 1 }} contentContainerStyle={{ gap: spacing[2], paddingBottom: spacing[4] }}>
        <Choice label={ko.blank} primary={chosen === null} onPress={() => onPick(null)} />
        {ids.map((id) => <Choice key={id} label={showLine(view, id) ?? ''} primary={chosen === id} onPress={() => onPick(id)} />)}
      </BottomSheetScrollView>
    </DragSheet>
  );
}
