import type { PanelAction } from '@/logic/info-panel';
import { compose, ko } from '@/locale/ko';

import { actionsForNode } from './_nodeActions';
import type { StoryGraphModel, StoryGraphNode } from './types';

export type NearbyItem = {
  id: string;
  kindLabel: string;
  title: string;
  body: string;
  action?: PanelAction;
};

export type NearbyPanelModel = {
  summary: string;
  items: NearbyItem[];
};

export function buildNearbyPanel(graph: StoryGraphModel): NearbyPanelModel {
  const people = graph.nodes.filter(isNearbyPerson);
  const places = graph.nodes.filter(isNearbyPlace);
  const items = graph.nodes.filter(isNearbyItem);
  const tasks = graph.nodes.filter((node) => node.kind === 'quest');
  return {
    summary: compose.nearbySummary(people.length, places.length, tasks.length, items.length),
    items: [
      ...people.map(personItem),
      ...places.map(placeItem),
      ...items.map(itemItem),
      ...tasks.map(taskItem),
    ],
  };
}

function isNearbyPerson(node: StoryGraphNode): boolean {
  return node.kind === 'subject' || (node.kind === 'target' && node.reachable);
}

function isNearbyPlace(node: StoryGraphNode): boolean {
  return node.kind === 'location' && node.reachable;
}

function isNearbyItem(node: StoryGraphNode): boolean {
  return node.kind === 'item' && node.reachable;
}

function personItem(node: StoryGraphNode): NearbyItem {
  if (node.kind === 'subject') {
    return {
      id: node.id,
      kindLabel: ko.legend.character,
      title: node.label,
      body: node.known[0] ?? node.role,
      action: {
        kind: 'text',
        label: ko.panel.talk,
        text: compose.talkTo(node.label),
      },
    };
  }
  if (node.kind !== 'target') {
    return {
      id: node.id,
      kindLabel: ko.legend.character,
      title: node.label,
      body: '',
      action: preferredAction(node),
    };
  }
  return {
    id: node.id,
    kindLabel: ko.legend.character,
    title: node.label,
    body: node.role,
    action: preferredAction(node),
  };
}

function placeItem(node: StoryGraphNode): NearbyItem {
  return {
    id: node.id,
    kindLabel: ko.legend.place,
    title: node.label,
    body: node.kind === 'location' ? node.description : '',
    action: preferredAction(node),
  };
}

function itemItem(node: StoryGraphNode): NearbyItem {
  return {
    id: node.id,
    kindLabel: ko.legend.item,
    title: node.label,
    body: node.kind === 'item' ? node.description : '',
    action: preferredAction(node),
  };
}

function taskItem(node: StoryGraphNode): NearbyItem {
  return {
    id: node.id,
    kindLabel: ko.legend.quest,
    title: node.label,
    body: node.kind === 'quest' ? node.summary : '',
    action: {
      kind: 'text',
      label: ko.panel.inspect,
      text: compose.inspect(node.label),
    },
  };
}

function preferredAction(node: StoryGraphNode): PanelAction | undefined {
  const actions = actionsForNode(node);
  return actions.find((action) => action.kind === 'text') ?? actions[0];
}
