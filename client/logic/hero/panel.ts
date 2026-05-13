import { characterMeta, formatGold, formatInventoryItem, joinOrDash, withDeath } from '@/components/ui';
import { ko } from '@/locale/ko';
import type { PanelSlot } from '@/logic/info-panel';

import type { EquipItem, Hero } from './types';

export function buildHeroSlot(hero: Hero, opts?: { chipShort?: string }): PanelSlot {
  const equipped = Object.values(hero.equipment).filter((it): it is EquipItem => it != null);
  return {
    id: 'hero',
    chip: { short: opts?.chipShort ?? ko.hero.chip, dot: hero.canLevelUp },
    panel: {
      title: withDeath(hero.name, hero.alive),
      meta: [{ text: characterMeta(hero.level, hero.raceJob, hero.gender) }],
      barSplit: [
        { label: 'HP', value: hero.hp, max: hero.hpMax, tone: 'hp', display: `${hero.hp}/${hero.hpMax}` },
        { label: 'MP', value: hero.mp, max: hero.mpMax, tone: 'mp', display: `${hero.mp}/${hero.mpMax}` },
      ],
      sections: [
        { label: ko.hero.ability, nodes: hero.stats.map((s): [string, number] => [s.label, s.value]) },
        { label: ko.hero.equip, text: joinOrDash(equipped.map((it) => it.name)) },
        { label: ko.hero.inventory, text: joinOrDash([formatGold(hero.gold), ...hero.inventory.map(formatInventoryItem)]) },
        { label: ko.hero.skill, text: joinOrDash(hero.skills) },
        { label: ko.hero.companion, text: joinOrDash(hero.companions) },
        { label: ko.panel.traits, text: joinOrDash(hero.status) },
      ],
    },
  };
}
