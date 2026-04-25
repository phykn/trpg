import type { Subject, Quest, Place } from '@/types/domain';
import type { PanelSlot } from '@/types/ui';

const periodOf = (h: number): string =>
  h < 5 ? '새벽' : h < 12 ? '오전' : h < 17 ? '오후' : h < 20 ? '저녁' : '밤';

export type GameSnapshot = {
  subject: Subject | null;
  quest: Quest | null;
  place: Place;
};

export function buildSubjectSlot(subject: Subject | null): PanelSlot {
  return {
    id: 'person',
    chip: subject
      ? { short: subject.role }
      : { short: '인물' },
    panel: subject ? {
      title: subject.name,
      meta: `Lv ${subject.level} · ${subject.race} ${subject.job}`,
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
        { label: '특징', text: subject.known.join(' · ') },
        { label: '소지', text: subject.inventory.map((i) => (i.qty > 1 ? `${i.name} ×${i.qty}` : i.name)).join(' · ') },
        { label: '능력', nodes: Object.entries(subject.stats) as [string, number][] },
      ],
    } : null,
  };
}

export function buildQuestSlot(quest: Quest | null): PanelSlot {
  return {
    id: 'quest',
    chip: { short: '퀘스트' },
    panel: quest ? {
      title: quest.title,
      meta: quest.giver,
      barSplit: [
        { label: '난이도', value: quest.difficulty.value, max: quest.difficulty.max, tone: 'bad', display: quest.difficulty.label },
        { label: '보상', parts: [
          { icon: 'wallet', text: `${quest.rewards.gold}`, tone: 'accent' },
          { icon: 'star',   text: `${quest.rewards.exp}`,  tone: 'exp' },
        ]},
      ],
      sections: [
        { label: '목표', text: quest.goals.join(' · ') },
        { label: '조건', text: quest.conditions.join(' · ') },
        { label: '메모', text: quest.memo },
      ],
    } : null,
  };
}

export function buildPlaceSlot(place: Place): PanelSlot {
  return {
    id: 'bg',
    chip: { short: '장소' },
    panel: {
      title: place.name,
      meta: place.date,
      bar: { label: '시간', value: place.hour, max: 24, tone: 'accent', display: `${place.hour}시 · ${periodOf(place.hour)}` },
      sections: [
        { label: '날씨', text: place.weather.join(' · ') },
        { label: '특징', text: place.features.join(' · ') },
        { label: '주변', text: place.surroundings.join(' · ') },
      ],
    },
  };
}

export function buildPanelSlots(state: GameSnapshot): PanelSlot[] {
  return [
    buildSubjectSlot(state.subject),
    buildQuestSlot(state.quest),
    buildPlaceSlot(state.place),
  ];
}
