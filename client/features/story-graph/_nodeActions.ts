import type { StoryGraphNode } from './presenters';
import type { PanelAction } from '@/types/ui';

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
    return { label: '이동', intent: moveIntent(node.label) };
  }
  if (node.status === 'reachable_meet') {
    return { label: '접근', intent: approachIntent(node.label) };
  }
  return null;
}
