import type { PanelAction } from '@/logic/info-panel';

import { compose, ko } from '@/locale/ko';
import type { StoryGraphNode } from './types';

export function actionForNode(node: StoryGraphNode): PanelAction | null {
  return actionsForNode(node)[0] ?? null;
}

export function actionsForNode(node: StoryGraphNode): PanelAction[] {
  if (node.status === 'reachable_move') {
    return [{
      kind: 'graph_action',
      label: ko.panel.move,
      graphAction: { verb: 'move', to: node.id },
      textFallback: compose.moveTo(node.label),
    }];
  }
  if (node.status === 'reachable_meet') {
    return [
      {
        kind: 'graph_action',
        label: ko.combat.attack,
        graphAction: { verb: 'attack', what: node.id },
        textFallback: compose.attack(node.label),
      },
      { kind: 'text', label: ko.panel.approach, text: compose.approachTo(node.label) },
    ];
  }
  if (node.status === 'reachable_item') {
    return [{ kind: 'text', label: ko.panel.pickup, text: compose.pickUp(node.label) }];
  }
  return [];
}
