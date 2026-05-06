import type { PanelAction } from '@/logic/info-panel';

import type { StoryGraphNode } from './types';

function moveIntent(name: string): string {
  const last = name.charCodeAt(name.length - 1);
  if (last < 0xac00 || last > 0xd7a3) return `${name}로 이동합니다`;
  const final = (last - 0xac00) % 28;
  if (final === 0 || final === 8) return `${name}로 이동합니다`;
  return `${name}으로 이동합니다`;
}

function approachIntent(name: string): string {
  // `에게` works for any final-jamo so no batchim split is needed.
  return `${name}에게 접근합니다`;
}

export function actionForNode(node: StoryGraphNode): PanelAction | null {
  if (node.status === 'reachable_move') {
    return { kind: 'text', label: '이동', text: moveIntent(node.label) };
  }
  if (node.status === 'reachable_meet') {
    return { kind: 'text', label: '접근', text: approachIntent(node.label) };
  }
  return null;
}
