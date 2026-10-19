import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Choice, Shell } from './CardShell';

export function CostCard({ due, onPick }: { due: GameView['due']; onPick: (action: string) => void }) {
  return (
    <Shell title={ko.costTitle}>
      {due.map((d) => <Choice key={d.action} label={d.name} sub={ko.weight[d.weight]} onPress={() => onPick(d.action)} />)}
    </Shell>
  );
}
