import type { EquipItem, Hero, Place, Quest, Subject } from '@/types/domain';
import type { PanelSlot } from '@/types/ui';

import { joinInventoryOrDash, joinOrDash } from './format';

type GameSnapshot = {
  hero: Hero;
  subject: Subject | null;
  quest: Quest | null;
  place: Place | null;
};

function buildHeroSlot(hero: Hero): PanelSlot {
  const equipped = Object.values(hero.equipment).filter((it): it is EquipItem => it !== null);
  return {
    id: 'hero',
    chip: { short: hero.name, dot: hero.canLevelUp },
    panel: {
      title: hero.name,
      meta: `Lv ${hero.level} · ${hero.raceJob}`,
      barSplit: [
        { label: 'HP', value: hero.hp, max: hero.hpMax, tone: 'hp', display: `${hero.hp}/${hero.hpMax}` },
        { label: 'MP', value: hero.mp, max: hero.mpMax, tone: 'mp', display: `${hero.mp}/${hero.mpMax}` },
      ],
      sections: [
        { label: '능력', nodes: hero.stats.map((s): [string, number] => [s.label, s.value]) },
        { label: '장비', text: joinOrDash(equipped.map((it) => it.name)) },
        { label: '소지', text: joinInventoryOrDash(hero.inventory) },
        { label: '기술', text: joinOrDash(hero.skills) },
        { label: '특징', text: joinOrDash(hero.status) },
        { label: '동료', text: joinOrDash(hero.companions) },
      ],
    },
  };
}

function buildSubjectSlot(subject: Subject | null): PanelSlot {
  if (!subject) return { id: 'person', chip: { short: '대상' }, panel: null };
  const equipped = Object.values(subject.equipment).filter((it): it is EquipItem => it !== null);
  return {
    id: 'person',
    chip: { short: '대상' },
    panel: {
      title: subject.name,
      meta: `Lv ${subject.level} · ${subject.raceJob}`,
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
        { label: '소지', text: joinInventoryOrDash(subject.inventory) },
        { label: '기술', text: joinOrDash(subject.skills) },
        { label: '특징', text: joinOrDash(subject.known) },
      ],
    },
  };
}

function buildQuestSlot(quest: Quest | null): PanelSlot {
  return {
    id: 'quest',
    chip: { short: '퀘스트' },
    panel: quest
      ? {
          title: quest.title,
          meta: quest.giver,
          barSplit: [
            { label: '난이도', value: quest.difficulty.value, max: quest.difficulty.max, tone: 'bad', display: quest.difficulty.label },
            {
              label: '보상',
              parts: [
                { label: '금', text: `${quest.rewards.gold}`, tone: 'accent' },
                { label: '경', text: `${quest.rewards.exp}`, tone: 'exp' },
              ],
            },
          ],
          sections: [
            { label: '목표', text: joinOrDash(quest.goals) },
            { label: '조건', text: joinOrDash(quest.conditions) },
            { label: '요약', text: quest.summary },
          ],
        }
      : null,
  };
}

function moveIntent(name: string): string {
  const last = name.charCodeAt(name.length - 1);
  if (last < 0xac00 || last > 0xd7a3) return `${name}로 이동`;
  const final = (last - 0xac00) % 28;
  if (final === 0 || final === 8) return `${name}로 이동`;
  return `${name}으로 이동`;
}

function buildPlaceSlot(place: Place | null): PanelSlot {
  return {
    id: 'bg',
    chip: { short: '이동' },
    panel: place
      ? {
          title: place.name,
          meta: joinOrDash(place.weather),
          sections: [{ label: '시간', text: place.dateTime }],
          actions: [
            {
              label: '장소',
              items: place.surroundings.map((s) => ({
                label: s.name,
                intent: moveIntent(s.name),
                confirm: {
                  title: s.name,
                  subtitle: s.difficulty ? `이동 난이도: ${s.difficulty}` : undefined,
                  blurb: s.blurb || undefined,
                  confirmLabel: '이동',
                },
              })),
            },
            {
              label: '대상',
              items: place.targets.map((t) => ({
                label: t.name,
                intent: `${t.name}에게 이동`,
                confirm: {
                  title: t.name,
                  subtitle: t.role || undefined,
                  blurb: t.blurb || undefined,
                  trust: t.trust !== 0 ? t.trust : undefined,
                  confirmLabel: '이동',
                },
              })),
            },
          ],
        }
      : null,
  };
}

export function buildPanelSlots(state: GameSnapshot): PanelSlot[] {
  return [
    buildHeroSlot(state.hero),
    buildSubjectSlot(state.subject),
    buildQuestSlot(state.quest),
    buildPlaceSlot(state.place),
  ];
}
