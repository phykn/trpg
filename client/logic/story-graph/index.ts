export type {
  Place,
  PlaceSurrounding,
  PlaceTarget,
  RiskBadge,
  StoryGraphModel,
} from './types';
import { ko } from '@/locale/ko';
import type { StoryGraphModel } from './types';

export const EMPTY_STORY_GRAPH: StoryGraphModel = {
  nodes: [],
  edges: [],
  summary: ko.panel.noStoryData,
};

export { buildNearbyPanel } from './nearby';
export type { NearbyItem, NearbyPanelModel } from './nearby';
