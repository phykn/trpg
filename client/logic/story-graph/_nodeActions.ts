import type { PanelAction } from '@/logic/info-panel';

import { compose, ko } from '@/locale/ko';
import type { StoryGraphNode } from './types';

export function actionForNode(node: StoryGraphNode): PanelAction | null {
  if (node.status === 'reachable_move') {
    return { kind: 'text', label: ko.panel.move, text: compose.moveTo(node.label) };
  }
  if (node.status === 'reachable_meet') {
    return { kind: 'text', label: ko.panel.approach, text: compose.approachTo(node.label) };
  }
  return null;
}
