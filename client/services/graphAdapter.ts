import { ko } from '@/locale/ko';

import type {
  FrontState,
  GraphCombatState,
  GraphFrontState,
  GraphHeroState,
  GraphPlaceTarget,
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
    subject: adaptSubject(selectSubjectTarget(state.place?.targets ?? [])),
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

export function deriveGraphSuggestions(state: GraphFrontState): string[] {
  if (state.pendingConfirmation !== null) return [];
  if (state.combat !== null) return combatSuggestions(state.combat);

  const suggestions: string[] = [];
  const livingTargets = state.place?.targets.filter((target) => target.hp.current > 0) ?? [];
  const enemy = livingTargets.find((target) => target.kind === 'enemy');
  if (enemy) suggestions.push(`${enemy.name}${objectParticle(enemy.name)} 공격한다`);

  for (const npc of livingTargets.filter((target) => target.kind === 'npc')) {
    suggestions.push(`${npc.name}에게 말을 건다`);
  }
  for (const exit of state.place?.exits ?? []) {
    suggestions.push(`${exit.name}${directionParticle(exit.name)} 이동한다`);
  }
  suggestions.push('주변을 살펴본다');
  return uniqueFirst(suggestions, 3);
}

function combatSuggestions(combat: GraphCombatState): string[] {
  const enemy = combat.participants.find(
    (participant) => participant.side === 'enemy' && participant.hp.current > 0,
  );
  const suggestions = enemy
    ? [`${enemy.name}${objectParticle(enemy.name)} 공격한다`, '방어한다', '도망친다']
    : ['방어한다', '도망친다'];
  return uniqueFirst(suggestions, 3);
}

function uniqueFirst(values: string[], limit: number): string[] {
  const result: string[] = [];
  for (const value of values) {
    if (result.includes(value)) continue;
    result.push(value);
    if (result.length >= limit) break;
  }
  return result;
}

function objectParticle(value: string): '을' | '를' {
  return hasFinalConsonant(value) ? '을' : '를';
}

function directionParticle(value: string): '으로' | '로' {
  const code = value.charCodeAt(value.length - 1);
  const jong = code >= 0xac00 && code <= 0xd7a3 ? (code - 0xac00) % 28 : 0;
  return jong !== 0 && jong !== 8 ? '으로' : '로';
}

function hasFinalConsonant(value: string): boolean {
  const code = value.charCodeAt(value.length - 1);
  if (code < 0xac00 || code > 0xd7a3) return false;
  return (code - 0xac00) % 28 !== 0;
}

function selectSubjectTarget(targets: GraphPlaceTarget[]): GraphPlaceTarget | null {
  return targets.find((target) => target.hp.current > 0) ?? targets[0] ?? null;
}

function adaptSubject(target: GraphPlaceTarget | null): FrontState['subject'] {
  if (target === null) return null;
  return {
    name: target.name,
    alive: target.hp.current > 0,
    role: '',
    raceJob: '',
    gender: '',
    trust: 0,
    known: [],
    level: 1,
    hp: target.hp.current,
    hpMax: target.hp.maximum,
    stats: [],
    equipment: EMPTY_EQUIPMENT,
    inventory: [],
    skills: [],
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
        id: enemy.id,
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
