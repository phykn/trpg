import { DASH, characterMeta, formatInventoryItem, joinOrDash } from '@/components/ui';
import type { EquipItem } from '@/features/hero';
import type { PanelSlot } from '@/features/info-panel';

import type { Subject } from './types';

function withDeath(name: string, alive: boolean | undefined): string {
  return alive === false ? `${name} (죽음)` : name;
}

export function buildSubjectSlot(subject: Subject | null): PanelSlot {
  if (!subject) {
    return {
      id: 'person',
      chip: { short: '대상' },
      panel: { empty: true, title: '대상' },
    };
  }
  const equipped = Object.values(subject.equipment).filter((it): it is EquipItem => it !== null);
  return {
    id: 'person',
    chip: { short: '대상' },
    panel: {
      title: withDeath(subject.name, subject.alive),
      meta: [{ text: characterMeta(subject.level, subject.raceJob, subject.gender) }],
      barSplit: [
        { label: 'HP', value: subject.hp, max: subject.hpMax, tone: 'hp', display: `${subject.hp}/${subject.hpMax}` },
        {
          label: '호감도',
          value: subject.trust,
          max: 100,
          tone: subject.trust >= 0 ? 'good' : 'bad',
          display: subject.trust > 0 ? `+${subject.trust}` : `${subject.trust}`,
          signed: true,
        },
      ],
      sections: [
        { label: '능력', nodes: subject.stats.map((s): [string, number] => [s.label, s.value]) },
        { label: '장비', text: joinOrDash(equipped.map((it) => it.name)) },
        { label: '소지', text: joinOrDash(subject.inventory.map(formatInventoryItem)) },
        { label: '기술', text: joinOrDash(subject.skills) },
        { label: '역할', text: subject.role || DASH },
        { label: '특징', text: joinOrDash(subject.known) },
      ],
    },
  };
}
