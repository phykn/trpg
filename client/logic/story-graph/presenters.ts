import { ko } from '@/locale/ko';
import type { Quest } from '@/logic/quest';

import type { RiskBadge, StoryGraphModel } from './types';

export const DEFAULT_RISK: RiskBadge = {
  label: ko.status.normalRisk,
  tone: 'neutral',
};

type StoryGraphSource = {
  hero: {
    id: string;
    name: string;
    resources: { hp: { current: number } };
  };
  place: {
    id: string;
    name: string;
    description: string;
    exits: { id: string; name: string; description: string }[];
    items?: { id: string; name: string; description: string }[];
    targets: {
      id: string;
      name: string;
      level?: number;
      raceJob: string;
      gender: string;
      role: string;
      alive: boolean;
    }[];
  } | null;
  quest: Quest | null;
  questOffers: Quest[];
};

export function buildStoryGraph(state: StoryGraphSource): StoryGraphModel {
  const place = state.place;
  if (place === null) {
    return {
      nodes: [
        {
          id: state.hero.id,
          label: state.hero.name,
          kind: 'hero',
          status: null,
          reachable: true,
          level: 1,
          raceJob: '',
          gender: '',
          role: '',
          alive: state.hero.resources.hp.current > 0,
        },
      ],
      edges: [],
      summary: state.hero.name,
    };
  }
  const placeItems = place.items ?? [];
  const quests = visibleQuests(state);

  return {
    nodes: [
      {
        id: state.hero.id,
        label: state.hero.name,
        kind: 'hero',
        status: null,
        reachable: true,
        level: 1,
        raceJob: '',
        gender: '',
        role: '',
        alive: state.hero.resources.hp.current > 0,
      },
      {
        id: place.id,
        label: place.name,
        kind: 'place',
        status: 'current',
        reachable: true,
        description: place.description,
        risk: DEFAULT_RISK,
        dayPhase: '',
        weather: [],
      },
      ...place.exits.map((exit) => ({
        id: exit.id,
        label: exit.name,
        kind: 'location' as const,
        status: 'reachable_move' as const,
        reachable: true,
        description: exit.description,
        risk: DEFAULT_RISK,
        moveDifficulty: null,
      })),
      ...placeItems.map((item) => ({
        id: item.id,
        label: item.name,
        kind: 'item' as const,
        status: 'reachable_item' as const,
        reachable: true as const,
        description: item.description,
      })),
      ...place.targets.map((target) => ({
        id: target.id,
        label: target.name,
        kind: 'target' as const,
        status: 'reachable_meet' as const,
        reachable: true,
        level: target.level ?? 1,
        raceJob: target.raceJob,
        gender: target.gender,
        role: target.role,
        alive: target.alive,
      })),
      ...quests.map((quest) => ({
        id: quest.id,
        label: quest.title,
        kind: 'quest' as const,
        status: null,
        reachable: true as const,
        questDifficulty: quest.difficulty.label,
        rewards: quest.rewards,
        giver: quest.giver,
        goals: quest.goals,
        summary: quest.summary,
        actions: quest.actions,
        choices: quest.choices ?? [],
      })),
    ],
    edges: [
      {
        id: `current:${state.hero.id}:${place.id}`,
        source: state.hero.id,
        target: place.id,
        label: ko.panel.here,
        kind: 'current_pin',
      },
      ...place.exits.map((exit) => ({
        id: `move:${place.id}:${exit.id}`,
        source: place.id,
        target: exit.id,
        label: ko.panel.move,
        kind: 'move' as const,
      })),
      ...placeItems.map((item) => ({
        id: `item:${place.id}:${item.id}`,
        source: place.id,
        target: item.id,
        label: ko.panel.pickup,
        kind: 'item' as const,
      })),
      ...place.targets.map((target) => ({
        id: `meet:${place.id}:${target.id}`,
        source: place.id,
        target: target.id,
        label: ko.panel.approach,
        kind: 'meet' as const,
      })),
      ...quests.map((quest) => ({
        id: `quest:${place.id}:${quest.id}`,
        source: place.id,
        target: quest.id,
        label: quest.status === 'active' ? ko.quest.name : ko.quest.offer,
        kind: 'quest_giver' as const,
      })),
    ],
    summary: place.name,
  };
}

function visibleQuests(state: Pick<StoryGraphSource, 'quest' | 'questOffers'>): Quest[] {
  const seen = new Set<string>();
  return [state.quest, ...state.questOffers].filter((quest): quest is Quest => {
    if (quest === null || seen.has(quest.id)) return false;
    seen.add(quest.id);
    return true;
  });
}
