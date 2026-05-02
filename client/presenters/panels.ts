import type { EquipItem, Hero, Quest, Subject } from '@/types/domain';
import type { MetaSegment, PanelSlot } from '@/types/ui';

import { DASH, characterMeta, formatInventoryItem, joinOrDash } from './format';

type GameSnapshot = {
  hero: Hero;
  subject: Subject | null;
  quest: Quest | null;
};

function plainMeta(text: string): MetaSegment[] {
  return [{ text }];
}

// Strict `alive === false`: undefined is not treated as dead since some SSE state events still omit the field.
function withDeath(name: string, alive: boolean | undefined): string {
  return alive === false ? `${name} (죽음)` : name;
}

function buildHeroSlot(hero: Hero): PanelSlot {
  const equipped = Object.values(hero.equipment).filter((it): it is EquipItem => it !== null);
  return {
    id: 'hero',
    chip: { short: hero.name, dot: hero.canLevelUp },
    panel: {
      title: withDeath(hero.name, hero.alive),
      meta: plainMeta(characterMeta(hero.level, hero.raceJob, hero.gender)),
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

function buildSubjectSlot(subject: Subject | null): PanelSlot {
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
      meta: plainMeta(characterMeta(subject.level, subject.raceJob, subject.gender)),
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

function buildQuestSlot(quest: Quest | null): PanelSlot {
  if (!quest) {
    return {
      id: 'quest',
      chip: { short: '퀘스트' },
      panel: { empty: true, title: '퀘스트' },
    };
  }
  return {
    id: 'quest',
    chip: { short: '퀘스트' },
    panel: {
      title: quest.title,
      meta: [{ text: quest.difficulty.label, tone: quest.difficulty.tone ?? undefined }],
      sections: [
        { label: '의뢰', text: quest.giver },
        { label: '보상', nodes: [['GOLD', quest.rewards.gold], ['EXP', quest.rewards.exp]] },
        { label: '목표', text: joinOrDash(quest.goals) },
        { label: '조건', text: joinOrDash(quest.conditions) },
        { label: '요약', text: quest.summary },
      ],
    },
  };
}

export function buildPanelSlots(state: GameSnapshot): PanelSlot[] {
  return [
    buildHeroSlot(state.hero),
    buildSubjectSlot(state.subject),
    buildQuestSlot(state.quest),
  ];
}
