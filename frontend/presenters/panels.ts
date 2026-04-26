import type { Place, Quest, Subject } from '@/types/domain';
import type { PanelSlot } from '@/types/ui';

import { joinInventory, joinList } from './format';

type GameSnapshot = {
  subject: Subject | null;
  quest: Quest | null;
  place: Place | null;
};

function buildSubjectSlot(subject: Subject | null): PanelSlot {
  return {
    id: 'person',
    chip: subject ? { short: subject.role } : { short: '인물' },
    panel: subject
      ? {
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
            { label: '특징', text: joinList(subject.known) },
            { label: '소지', text: joinInventory(subject.inventory) },
            { label: '능력', nodes: Object.entries(subject.stats) as [string, number][] },
          ],
        }
      : null,
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
                { icon: 'wallet', text: `${quest.rewards.gold}`, tone: 'accent' },
                { icon: 'star', text: `${quest.rewards.exp}`, tone: 'exp' },
              ],
            },
          ],
          sections: [
            { label: '목표', text: joinList(quest.goals) },
            { label: '조건', text: joinList(quest.conditions) },
            { label: '요약', text: quest.summary },
          ],
        }
      : null,
  };
}

function buildPlaceSlot(place: Place | null): PanelSlot {
  return {
    id: 'bg',
    chip: { short: '장소' },
    panel: place
      ? {
          title: place.name,
          meta: place.date,
          bar: { label: '시간', value: place.hour, max: 24, tone: 'accent', display: `${place.hour}시 · ${place.period}` },
          sections: [
            { label: '날씨', text: joinList(place.weather) },
            { label: '특징', text: joinList(place.features) },
            { label: '주변', text: joinList(place.surroundings) },
          ],
        }
      : null,
  };
}

export function buildPanelSlots(state: GameSnapshot): PanelSlot[] {
  return [
    buildSubjectSlot(state.subject),
    buildQuestSlot(state.quest),
    buildPlaceSlot(state.place),
  ];
}
