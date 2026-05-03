import { characterMeta, formatInventoryItem, joinOrDash } from '@/components/ui';
import type { PanelSlot } from '@/features/info-panel';

import type { EquipItem, Hero } from './types';

function withDeath(name: string, alive: boolean | undefined): string {
  return alive === false ? `${name} (죽음)` : name;
}

export function buildHeroSlot(hero: Hero): PanelSlot {
  const equipped = Object.values(hero.equipment).filter((it): it is EquipItem => it !== null);
  return {
    id: 'hero',
    chip: { short: hero.name, dot: hero.canLevelUp },
    panel: {
      title: withDeath(hero.name, hero.alive),
      meta: [{ text: characterMeta(hero.level, hero.raceJob, hero.gender) }],
      barSplit: [
        { label: 'HP', value: hero.hp, max: hero.hpMax, tone: 'hp', display: `${hero.hp}/${hero.hpMax}` },
        { label: 'MP', value: hero.mp, max: hero.mpMax, tone: 'mp', display: `${hero.mp}/${hero.mpMax}` },
      ],
      sections: [
        { label: '능력', nodes: hero.stats.map((s): [string, number] => [s.label, s.value]) },
        { label: '장비', text: joinOrDash(equipped.map((it) => it.name)) },
        { label: '소지', text: joinOrDash(hero.inventory.map(formatInventoryItem)) },
        { label: '기술', text: joinOrDash(hero.skills) },
        { label: '동료', text: joinOrDash(hero.companions) },
        { label: '특징', text: joinOrDash(hero.status) },
      ],
    },
  };
}
