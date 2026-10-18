import { Reader } from '@/components/ui/Reader';
import { ko } from '@/locale/ko';
import type { GameView, Named } from '@/services/types';

const list = (items: Named[]) => (items.length ? items.map((x) => `· ${x.name}${x.text ? `: ${x.text}` : ''}`).join('\n') : ko.none);

export function Sheet({ view }: { view: GameView }) {
  const p = view.player;
  const text = [
    `${ko.approaches}\n${p.approaches.map((a) => `· ${a.name} ${ko.approachPlus(a.value)}`).join('\n')}`,
    `${ko.traits}\n${list(p.traits)}`,
    `${ko.wounds(p.wounds)} · ${ko.gold(p.gold)}`,
    `${ko.items}\n${list(p.items)}`,
    `${ko.knowledge}\n${list(p.knowledge)}`,
    `${ko.people}\n${view.people.length ? view.people.map((x) => `· ${x.name} (${x.role}) · ${x.mood}`).join('\n') : ko.none}`,
    `${ko.quests}\n${list(view.quests)}`,
  ].join('\n\n');
  return <Reader text={text} />;
}
