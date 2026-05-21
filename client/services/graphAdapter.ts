import { ko } from '@/locale/ko';

import type {
  FrontState,
  GraphCombatState,
  GraphFrontState,
  GraphHeroState,
  GraphPlaceTarget,
  GraphPlaceState,
} from './wire';

const STAT_ORDER = ['body', 'mind', 'agility', 'presence'] as const;

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
    subject: adaptSubject(selectSubjectTarget(state.place?.targets ?? [])),
    chapter: state.chapter,
    scenarioCompleted: state.scenarioCompleted,
    quest: state.quest,
    questOffers: state.questOffers,
    place: adaptPlace(state.place),
    combat: adaptCombat(state.combat),
    log: state.log,
    pendingConfirmation: state.pendingConfirmation,
    pendingRoll: state.pendingRoll,
    storyGraph: buildStoryGraph(state, visibleQuests(state)),
  };
}

function selectSubjectTarget(targets: GraphPlaceTarget[]): GraphPlaceTarget | null {
  return targets.find((target) => target.alive) ?? targets[0] ?? null;
}

function adaptSubject(target: GraphPlaceTarget | null): FrontState['subject'] {
  if (target === null) return null;
  return {
    name: target.name,
    alive: target.alive,
    role: target.role,
    raceJob: target.raceJob,
    gender: target.gender,
    level: target.level ?? 1,
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
    gold: hero.gold,
    stats: statEntries(hero.stats),
    equipment: hero.equipment ?? EMPTY_EQUIPMENT,
    inventory: hero.inventory ?? [],
    skills: hero.skills ?? [],
    companions: [],
    status: hero.status ?? [],
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
    })),
    risk: DEFAULT_RISK,
  };
}

function adaptCombat(combat: GraphCombatState | null): FrontState['combat'] {
  if (combat === null) return null;
  return {
    round: combat.round,
    outcome: combat.outcome,
    turnLabel: ko.combat.label,
    playerHearts: combat.playerHearts,
    enemyHearts: combat.enemyHearts,
    availableSupports: combat.availableSupports ?? [],
    escapeReady: combat.escapeReady ?? false,
    enemyPressure: combat.enemyPressure ?? 0,
    lastRoll: combat.lastRoll ?? null,
    lastDc: combat.lastDc ?? null,
    enemies: combat.participants
      .filter((participant) => participant.side === 'enemy')
      .map((enemy) => ({
        id: enemy.id,
        name: enemy.name,
        alive: enemy.id === combat.activeEnemyId && combat.enemyHearts.current > 0,
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
        },
      ],
      edges: [],
      summary: state.hero.name,
    };
  }
  const placeItems = place.items ?? [];

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
