// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act } from 'react-test-renderer';

import { ko } from '@/locale/ko';
import {
  getStoryContract,
  getStoryDebt,
  getStoryGraph,
  getStoryPatchTimeline,
  previewStoryContract,
  previewStoryPatch,
  replayStoryPrompt,
  rollbackStoryPatch,
  updateStoryContract,
} from '@/services';

import { StoryDevPanel } from '../StoryDevPanel';

jest.mock('@/services', () => ({
  getStoryContract: jest.fn(),
  getStoryDebt: jest.fn(),
  getStoryGraph: jest.fn(),
  getStoryPatchTimeline: jest.fn(),
  previewStoryContract: jest.fn(),
  previewStoryPatch: jest.fn(),
  replayStoryPrompt: jest.fn(),
  rollbackStoryPatch: jest.fn(),
  updateStoryContract: jest.fn(),
}));

const mockedGetStoryContract = getStoryContract as jest.Mock;
const mockedGetStoryDebt = getStoryDebt as jest.Mock;
const mockedGetStoryGraph = getStoryGraph as jest.Mock;
const mockedGetStoryPatchTimeline = getStoryPatchTimeline as jest.Mock;
const mockedPreviewStoryContract = previewStoryContract as jest.Mock;
const mockedPreviewStoryPatch = previewStoryPatch as jest.Mock;
const mockedReplayStoryPrompt = replayStoryPrompt as jest.Mock;
const mockedRollbackStoryPatch = rollbackStoryPatch as jest.Mock;
const mockedUpdateStoryContract = updateStoryContract as jest.Mock;

function timelinePayload() {
  return {
    game_id: 'game-1',
    entries: [
      {
        turn: 2,
        status: 'accepted',
        intentKind: 'clue_candidate',
        reason: '젖은 표를 발견했습니다.',
        patches: [{ op: 'add_clue', id: 'clue_wet_ticket' }],
        rejectedReasons: [],
        changedNodeIds: ['clue_wet_ticket'],
        changedEdgeIds: ['has_knowledge:loc_01:clue_wet_ticket'],
      },
    ],
  };
}

function debtPayload() {
  return {
    game_id: 'game-1',
    debt: {
      unresolvedClues: [
        {
          id: 'clue_wet_ticket',
          title: '젖은 표',
          turn: 2,
          reason: 'generated clue is not marked resolved',
        },
      ],
      orphanCharacters: [],
      orphanItems: [],
      danglingQuestBeats: [],
    },
  };
}

function graphPayload() {
  return {
    game_id: 'game-1',
    graph: {
      nodes: {
        loc_01: {
          id: 'loc_01',
          type: 'location',
          properties: { name: '안개 항구' },
        },
      },
      edges: {},
    },
  };
}

function contractPayload() {
  return {
    game_id: 'game-1',
    contract: {
      id: 'white_isle_llm',
      world: { title: '흰섬으로 가는 안개 바다', locale: 'ko' },
      fixed: ['엘리는 시작부터 동행합니다.'],
      forbid: ['결말을 조기 공개하지 않습니다.'],
      tone: { register: '합니다체', person: 'second' },
      budgets: { patches_per_turn: 1, new_terms_per_turn: 1 },
      allowed_ops: ['add_clue'],
      stability_defaults: { add_clue: 'scene' },
    },
  };
}

beforeEach(() => {
  mockedGetStoryContract.mockReset();
  mockedGetStoryPatchTimeline.mockReset();
  mockedGetStoryDebt.mockReset();
  mockedGetStoryGraph.mockReset();
  mockedPreviewStoryContract.mockReset();
  mockedPreviewStoryPatch.mockReset();
  mockedReplayStoryPrompt.mockReset();
  mockedRollbackStoryPatch.mockReset();
  mockedUpdateStoryContract.mockReset();
  mockedGetStoryContract.mockResolvedValue(contractPayload());
  mockedGetStoryPatchTimeline.mockResolvedValue(timelinePayload());
  mockedGetStoryDebt.mockResolvedValue(debtPayload());
  mockedGetStoryGraph.mockResolvedValue(graphPayload());
});

test('renders dashboard, timeline, and debt loaded from story dev APIs', async () => {
  let root: renderer.ReactTestRenderer | null = null;
  await act(async () => {
    root = renderer.create(<StoryDevPanel gameId="game-1" onClose={jest.fn()} />);
  });

  expect(JSON.stringify(root!.toJSON())).toContain(ko.storyDev.patchCount);
  expect(JSON.stringify(root!.toJSON())).toContain('game-1');
  expect(mockedGetStoryPatchTimeline).toHaveBeenCalledWith('game-1');
  expect(mockedGetStoryDebt).toHaveBeenCalledWith('game-1');
  expect(mockedGetStoryGraph).toHaveBeenCalledWith('game-1');
  expect(mockedGetStoryContract).toHaveBeenCalledWith('game-1');

  const graphTab = root!.root.findByProps({ accessibilityLabel: ko.storyDev.graph });
  await act(async () => {
    graphTab.props.onPress();
  });

  expect(JSON.stringify(root!.toJSON())).toContain('loc_01');
  expect(JSON.stringify(root!.toJSON())).toContain('안개 항구');

  const timelineTab = root!.root.findByProps({ accessibilityLabel: ko.storyDev.timeline });
  await act(async () => {
    timelineTab.props.onPress();
  });

  expect(JSON.stringify(root!.toJSON())).toContain('젖은 표를 발견했습니다.');

  const debtTab = root!.root.findByProps({ accessibilityLabel: ko.storyDev.debt });
  await act(async () => {
    debtTab.props.onPress();
  });

  expect(JSON.stringify(root!.toJSON())).toContain('젖은 표');
  expect(JSON.stringify(root!.toJSON())).toContain('generated clue is not marked resolved');
});

test('previews a contract edit from the contract tab', async () => {
  mockedPreviewStoryContract.mockResolvedValue({
    game_id: 'game-1',
    ok: true,
    reasons: [],
    contract: contractPayload().contract,
  });
  let root: renderer.ReactTestRenderer | null = null;
  await act(async () => {
    root = renderer.create(<StoryDevPanel gameId="game-1" onClose={jest.fn()} />);
  });

  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.contract }).props.onPress();
  });
  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.contractInput }).props.onChangeText(
      '{"id":"white_isle_llm","allowed_ops":["add_clue"]}',
    );
  });
  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.contractRun }).props.onPress();
  });

  expect(mockedPreviewStoryContract).toHaveBeenCalledWith('game-1', {
    id: 'white_isle_llm',
    allowed_ops: ['add_clue'],
  });
  expect(JSON.stringify(root!.toJSON())).toContain(ko.storyDev.contractOk);
});

test('applies a contract edit from the contract tab and reloads', async () => {
  mockedUpdateStoryContract.mockResolvedValue({
    game_id: 'game-1',
    contract: {
      ...contractPayload().contract,
      id: 'white_isle_llm_override',
    },
  });
  let root: renderer.ReactTestRenderer | null = null;
  await act(async () => {
    root = renderer.create(<StoryDevPanel gameId="game-1" onClose={jest.fn()} />);
  });

  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.contract }).props.onPress();
  });
  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.contractInput }).props.onChangeText(
      '{"id":"white_isle_llm_override","allowed_ops":["add_clue"]}',
    );
  });
  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.contractApply }).props.onPress();
  });

  expect(mockedUpdateStoryContract).toHaveBeenCalledWith('game-1', {
    id: 'white_isle_llm_override',
    allowed_ops: ['add_clue'],
  });
  expect(mockedGetStoryContract).toHaveBeenCalledTimes(2);
});

test('previews a patch proposal from the preview tab', async () => {
  mockedPreviewStoryPatch.mockResolvedValue({
    game_id: 'game-1',
    ok: true,
    reasons: [],
    changedNodeIds: ['clue_preview'],
    changedEdgeIds: ['has_knowledge:loc_01:clue_preview'],
  });
  let root: renderer.ReactTestRenderer | null = null;
  await act(async () => {
    root = renderer.create(<StoryDevPanel gameId="game-1" onClose={jest.fn()} />);
  });

  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.preview }).props.onPress();
  });
  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.previewInput }).props.onChangeText(
      '{"reason":"preview","patches":[{"op":"add_clue","id":"clue_preview"}]}',
    );
  });
  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.previewRun }).props.onPress();
  });

  expect(mockedPreviewStoryPatch).toHaveBeenCalledWith('game-1', {
    reason: 'preview',
    patches: [{ op: 'add_clue', id: 'clue_preview' }],
  });
  expect(JSON.stringify(root!.toJSON())).toContain(ko.storyDev.previewOk);
});

test('replays a writer prompt from the prompt tab', async () => {
  mockedReplayStoryPrompt.mockResolvedValue({
    game_id: 'game-1',
    agent: 'story_write',
    intent: { kind: 'clue_candidate', reason: 'perception action' },
    system_prompt: 'write only patches',
    user_payload: {
      player_input: '표를 살핍니다.',
      action: { verb: 'perceive', what: 'ticket' },
    },
  });
  let root: renderer.ReactTestRenderer | null = null;
  await act(async () => {
    root = renderer.create(<StoryDevPanel gameId="game-1" onClose={jest.fn()} />);
  });

  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.prompt }).props.onPress();
  });
  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.promptInput }).props.onChangeText(
      '{"player_input":"표를 살핍니다.","action":{"verb":"perceive","what":"ticket"}}',
    );
  });
  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.promptRun }).props.onPress();
  });

  expect(mockedReplayStoryPrompt).toHaveBeenCalledWith('game-1', {
    player_input: '표를 살핍니다.',
    action: { verb: 'perceive', what: 'ticket' },
  });
  expect(JSON.stringify(root!.toJSON())).toContain('write only patches');
  expect(JSON.stringify(root!.toJSON())).toContain('clue_candidate');
});

test('rolls back the latest patch and reloads the panel', async () => {
  mockedRollbackStoryPatch.mockResolvedValue({
    game_id: 'game-1',
    entry: {
      ...timelinePayload().entries[0],
      status: 'rolled_back',
    },
  });
  let root: renderer.ReactTestRenderer | null = null;
  await act(async () => {
    root = renderer.create(<StoryDevPanel gameId="game-1" onClose={jest.fn()} />);
  });

  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.timeline }).props.onPress();
  });
  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.rollback }).props.onPress();
  });

  expect(mockedRollbackStoryPatch).toHaveBeenCalledWith('game-1');
  expect(mockedGetStoryPatchTimeline).toHaveBeenCalledTimes(2);
  expect(mockedGetStoryDebt).toHaveBeenCalledTimes(2);
  expect(mockedGetStoryGraph).toHaveBeenCalledTimes(2);
  expect(mockedGetStoryContract).toHaveBeenCalledTimes(2);
});

test('does not enable rollback for skipped or empty accepted patches', async () => {
  mockedGetStoryPatchTimeline.mockResolvedValue({
    game_id: 'game-1',
    entries: [
      {
        turn: 1,
        status: 'skipped',
        intentKind: 'both',
        reason: 'nothing durable changed',
        patches: [],
        rejectedReasons: [],
        changedNodeIds: [],
        changedEdgeIds: [],
      },
      {
        turn: 2,
        status: 'accepted',
        intentKind: 'both',
        reason: 'legacy no-op entry',
        patches: [],
        rejectedReasons: [],
        changedNodeIds: [],
        changedEdgeIds: [],
      },
    ],
  });
  let root: renderer.ReactTestRenderer | null = null;
  await act(async () => {
    root = renderer.create(<StoryDevPanel gameId="game-1" onClose={jest.fn()} />);
  });

  await act(async () => {
    root!.root.findByProps({ accessibilityLabel: ko.storyDev.timeline }).props.onPress();
  });

  const rollback = root!.root.findByProps({ accessibilityLabel: ko.storyDev.rollback });
  expect(rollback.props.accessibilityState).toEqual({ disabled: true });
  expect(rollback.props.onPress).toBeUndefined();
});
