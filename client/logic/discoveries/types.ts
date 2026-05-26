export type DiscoveryEntry = {
  id: string;
  title: string;
  summary: string;
  stability: 'scene' | 'chapter' | 'campaign' | 'core';
  turnId?: number | null;
};

export type Discoveries = {
  memories: DiscoveryEntry[];
  clues: DiscoveryEntry[];
};
