import type { GameView, Group, Line } from '@/services/types';

export const GROUPS: Group[] = ['places', 'people', 'items', 'seen', 'heard'];

export function findLine(view: GameView, id: number): { group: Group; line: Line } | null {
  for (const group of GROUPS) {
    const line = view.notebook[group].find((l) => l.id === id);
    if (line) return { group, line };
  }
  return null;
}
