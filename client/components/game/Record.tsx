import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Group, Item, Row } from './Row';

export function Record({ journal }: { journal: GameView['journal'] }) {
  const owes = journal.owes;
  const beliefs = journal.beliefs.filter((b) => b.here);
  if (!owes.length && !beliefs.length) return null;
  return (
    <Group>
      <Row label={ko.row.record}>
        {owes.map((o) => (
          <Item key={`${o.debtor}${o.creditor}${o.kind}`} tone="gold">
            {o.kind === 'promise' ? ko.promise(o.name, o.promise) : ko.kindness(o.name)}
          </Item>
        ))}
        {beliefs.map((b) => <Item key={b.id} tone="muted">{ko.belief}: {b.text}</Item>)}
      </Row>
    </Group>
  );
}
