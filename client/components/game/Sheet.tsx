import { View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { Reader } from '@/components/ui/Reader';
import { ko } from '@/locale/ko';
import type { GameView, Named } from '@/services/types';

const list = (items: Named[]) => (items.length ? items.map((x) => `· ${x.name}${x.text ? `: ${x.text}` : ''}`).join('\n') : ko.none);

export function Sheet({ view, onNew }: { view: GameView; onNew: () => void }) {
  const p = view.player;
  const text = [
    `${ko.situation}\n${view.intro}`,
    `${ko.approaches}\n${p.approaches.map((a) => `· ${a.name} ${ko.approachPlus(a.value)}`).join('\n')}`,
    `${ko.traits}\n${list(p.traits)}`,
    `${ko.wounds(p.wounds)} · ${ko.gold(p.gold)}`,
    `${ko.items}\n${list(p.items)}`,
    p.skills.length ? `${ko.skills}\n${list(p.skills)}` : '',
    `${ko.knowledge}\n${list(p.knowledge)}`,
    `${ko.people}\n${view.people.length ? view.people.map((x) => `· ${x.name} (${x.role}) · ${x.mood}`).join('\n') : ko.none}`,
    view.quests.length ? `${ko.quests}\n${list(view.quests)}` : '',
    `${ko.exits}\n${view.exits.length ? view.exits.map((x) => `· ${x.label}${x.enabled ? '' : ` (${ko.closed})`}`).join('\n') : ko.none}`,
  ].filter(Boolean).join('\n\n');
  return (
    <View className="flex-1 min-h-0 gap-3">
      <Reader text={text} />
      <Button label={ko.newGame} onPress={onNew} />
    </View>
  );
}
