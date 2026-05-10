import { ko } from '@/locale/ko';

import type {
  FrontState,
  GraphCombatState,
  GraphFrontState,
  GraphHeroState,
  GraphPlaceState,
} from './wire';

const STAT_ORDER = ['body', 'agility', 'mind', 'presence'] as const;

const DEFAULT_RISK = {
  label: ko.status.normalRisk,
  tone: 'neutral' as const,
};

const EMPTY_EQUIPMENT = {
  weapon: null,
  armor: null,
  accessory: null,
};

export function adaptGraphState(state: GraphFrontState): FrontState {
  return {
    hero: adaptHero(state.hero),
    subject: null,
    quest: state.quest,
    questOffers: state.questOffers,
    place: adaptPlace(state.place),
    combat: adaptCombat(state.combat),
    log: state.log,
    pendingCheck: null,
    pendingConfirmation: state.pendingConfirmation,
    storyGraph: buildStoryGraph(state, visibleQuests(state)),
  };
}

function adaptHero(hero: GraphHeroState): FrontState['hero'] {
  const hp = hero.resources.hp;
  const mp = hero.resources.mp;
  return {
    name: hero.name,
    alive: hp.current > 0,
    raceJob: '',
    gender: '',
    level: hero.level,
    exp: hero.exp,
    expMax: hero.expMax,
    canLevelUp: hero.canLevelUp,
    hp: hp.current,
    hpMax: hp.maximum,
    mp: mp.current,
    mpMax: mp.maximum,
    reviveCoins: 0,
    reviveCoinsMax: 0,
    gold: hero.gold,
    stats: statEntries(hero.stats),
    equipment: EMPTY_EQUIPMENT,
    inventory: [],
    status: [],
    skills: [],
    companions: [],
  };
}

function adaptPlace(place: GraphPlaceState | null): FrontState['place'] {
  if (place === null) return null;
  return {
    name: place.name,
    description: place.description,
    dayPhase: '',
    weather: [],
    surroundings: place.exits.map((exit) => ({
      name: exit.name,
      blurb: exit.description,
      risk: DEFAULT_RISK,
    })),
    targets: place.targets.map((target) => ({
      name: target.name,
      level: 1,
      raceJob: '',
      gender: '',
      blurb: '',
      trust: 0,
    })),
    risk: DEFAULT_RISK,
  };
}

function adaptCombat(combat: GraphCombatState | null): FrontState['combat'] {
  if (combat === null) return null;
  return {
    round: combat.round,
    turnLabel: ko.combat.label,
    enemies: combat.participants
      .filter((participant) => participant.side === 'enemy')
      .map((enemy) => ({
        name: enemy.name,
        hp: enemy.hp.current,
        hpMax: enemy.hp.maximum,
        alive: enemy.hp.current > 0,
      })),
  };
}

function buildStoryGraph(
  state: GraphFrontState,
  quests: NonNullable<FrontState['quest']>[],
): FrontState['storyGraph'] {
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
          known: [],
        },
      ],
      edges: [],
      summary: state.hero.name,
    };
  }

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
        known: [],
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
      ...place.targets.map((target) => ({
        id: target.id,
        label: target.name,
        kind: 'target' as const,
        status: 'reachable_meet' as const,
        reachable: true,
        level: 1,
        raceJob: '',
        gender: '',
        role: '',
        alive: target.hp.current > 0,
        trust: 0,
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

function visibleQuests(state: GraphFrontState): NonNullable<FrontState['quest']>[] {
  const seen = new Set<string>();
  return [state.quest, ...state.questOffers].filter((quest): quest is NonNullable<FrontState['quest']> => {
    if (quest === null || seen.has(quest.id)) return false;
    seen.add(quest.id);
    return true;
  });
}

function statEntries(stats: Record<string, number>): FrontState['hero']['stats'] {
  const known = STAT_ORDER.filter((key) => Number.isFinite(stats[key])).map((key) => ({
    label: ko.ability[key],
    value: stats[key],
  }));
  const extras = Object.entries(stats)
    .filter(([key, value]) => !STAT_ORDER.includes(key as (typeof STAT_ORDER)[number]) && Number.isFinite(value))
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => ({ label: key, value }));
  return [...known, ...extras];
}
