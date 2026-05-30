import type { CombatBadge } from '@/logic/combat';
import type { Discoveries } from '@/logic/discoveries';
import type { Hero } from '@/logic/hero';
import type { LogEntry } from '@/logic/log';
import type { Quest } from '@/logic/quest';
import type { PendingRoll } from '@/logic/roll';
import type { Place, StoryGraphModel } from '@/logic/story-graph';
import type { Subject } from '@/logic/subject';

import type { SuggestionChip } from '../suggestions';
import type { Chapter } from './graphState';

export type PendingConfirmation = {
  id: string;
  kind: string;
  title: string;
  body: string;
  confirmLabel: string;
  cancelLabel: string;
  targetLabel?: string | null;
};

export type FrontState = {
  hero: Hero;
  subject: Subject | null;
  chapter: Chapter | null;
  scenarioCompleted: boolean;
  quest: Quest | null;
  questOffers: Quest[];
  place: Place | null;
  combat: CombatBadge | null;
  discoveries: Discoveries;
  log: LogEntry[];
  pendingConfirmation?: PendingConfirmation | null;
  pendingRoll?: PendingRoll | null;
  storyGraph: StoryGraphModel;
};

export type RaceCard = {
  id: string;
  name: string;
  description: string;
};

export type ProfileCard = {
  id: string;
  name: string;
  description: string;
  races: RaceCard[];
};

type PlayerInput = {
  name: string;
  race_id: string;
  gender: 'male' | 'female';
};

export type InitRequest = {
  profile: string;
  player: PlayerInput;
  locale: 'ko' | 'en';
};

export type SessionPayload = {
  game_id: string;
  state: FrontState;
  suggestions?: SuggestionChip[];
};
