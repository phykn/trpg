import { ko } from '@/locale/ko';
import { buildStoryGraph, DEFAULT_RISK } from '@/logic/story-graph';

import type {
  FrontState,
  GraphCombatState,
  GraphFrontState,
  GraphHeroState,
  GraphPlaceTarget,
  GraphPlaceState,
} from './wire';

const STAT_ORDER = ['body', 'mind', 'agility', 'presence'] as const;

const EMPTY_EQUIPMENT = {
  weapon: null,
  armor: null,
  accessory: null,
};

const EMPTY_DISCOVERIES = {
  memories: [],
  clues: [],
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
    discoveries: state.discoveries ?? EMPTY_DISCOVERIES,
    log: state.log,
    pendingConfirmation: state.pendingConfirmation,
    pendingRoll: state.pendingRoll,
    storyGraph: buildStoryGraph(state),
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
      canAttack: target.canAttack,
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
