import { DASH, characterMeta, formatGold, formatInventoryItem, joinOrDash, withDeath } from '@/components/ui';
import { ko } from '@/locale/ko';
import type { EquipItem } from '@/logic/hero';
import type { PanelSlot } from '@/logic/info-panel';

import type { Subject } from './types';

export function buildSubjectSlot(subject: Subject | null, opts?: { dot?: boolean }): PanelSlot {
  if (!subject) {
    return {
      id: 'person',
      chip: { short: ko.subject.chip, dot: opts?.dot },
      panel: { empty: true, title: ko.subject.chip },
    };
  }
  const equipped = Object.values(subject.equipment).filter((it): it is EquipItem => it !== null);
  return {
    id: 'person',
    chip: { short: ko.subject.chip, dot: opts?.dot },
    panel: {
      title: withDeath(subject.name, subject.alive),
      meta: [{ text: characterMeta(subject.level, subject.raceJob, subject.gender) }],
      bar: {
        label: ko.panel.affinity,
        value: subject.trust,
        max: 100,
        tone: subject.trust > 0 ? 'good' : subject.trust < 0 ? 'bad' : 'neutral',
        display: subject.trust > 0 ? `+${subject.trust}` : `${subject.trust}`,
        signed: true,
      },
      sections: [
        { label: ko.hero.ability, nodes: subject.stats.map((s): [string, number] => [s.label, s.value]) },
        { label: ko.hero.equip, text: joinOrDash(equipped.map((it) => it.name)) },
        {
          label: ko.hero.inventory,
          text: joinOrDash([
            ...(subject.gold === undefined ? [] : [formatGold(subject.gold)]),
            ...subject.inventory.map(formatInventoryItem),
          ]),
        },
        { label: ko.hero.skill, text: joinOrDash(subject.skills) },
        { label: ko.panel.role, text: subject.role || DASH },
        { label: ko.panel.traits, text: joinOrDash(subject.known) },
      ],
    },
  };
}
