export type NamedText = { id: string; name: string; text: string };

export type GameCatalog = {
  title: string;
  synopsis: string;
  roles: NamedText[];
};

export type GameAction = {
  id: string;
  target: string;
  label: string;
  description: string;
  cost: string;
  enabled: boolean;
  blocked: string;
  confirm: boolean;
  group: 'story' | 'move' | 'combat' | 'item' | 'growth';
};

export type GameView = {
  game_id: string;
  revision: number;
  title: string;
  player_name: string;
  role: string;
  hp: number;
  max_hp: number;
  mp: number;
  max_mp: number;
  gold: number;
  scene: NamedText;
  characters: NamedText[];
  objective: string;
  clock: string;
  remaining: number;
  alert: string;
  actions: GameAction[];
  knowledge: NamedText[];
  inventory: NamedText[];
  skills: NamedText[];
  journal: { turn: number; kind: 'story' | 'action' | 'roll' | 'world'; text: string }[];
  combat: {
    opponent: string;
    player_hearts: number;
    enemy_hearts: number;
    understanding: number;
    round: number;
  } | null;
  ending: (NamedText & { epilogue: string[] }) | null;
};

export type GameCommand = { option_id: string; revision: number; request_id: string };
