import React from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { Chip, Surface } from '@/components/ui';
import { ko } from '@/locale/ko';
import { ContractEditor, Preview, PromptReplay } from './StoryDevEditors';
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
import type {
  StoryContract,
  StoryContractPreviewResponse,
  StoryDebt,
  StoryDebtEntry,
  StoryGraph,
  StoryPatchLedgerEntry,
  StoryPatchPreviewResponse,
  StoryPromptReplayRequest,
  StoryPromptReplayResponse,
} from '@/services/wire';

type Props = {
  gameId: string;
  onClose: () => void;
};

type Tab = 'dashboard' | 'graph' | 'timeline' | 'debt' | 'contract' | 'prompt' | 'preview';

type State = {
  loading: boolean;
  error: string | null;
  entries: StoryPatchLedgerEntry[];
  debt: StoryDebt | null;
  graph: StoryGraph | null;
  contract: StoryContract | null;
};

const EMPTY_STATE: State = {
  loading: false,
  error: null,
  entries: [],
  debt: null,
  graph: null,
  contract: null,
};

const STORY_DEV_TABS: { id: Tab; label: string }[] = [
  { id: 'dashboard', label: ko.storyDev.dashboard },
  { id: 'timeline', label: ko.storyDev.timeline },
  { id: 'graph', label: ko.storyDev.graph },
  { id: 'debt', label: ko.storyDev.debt },
  { id: 'contract', label: ko.storyDev.contract },
  { id: 'prompt', label: ko.storyDev.prompt },
  { id: 'preview', label: ko.storyDev.preview },
];

export function StoryDevPanel({ gameId, onClose }: Props) {
  const [tab, setTab] = React.useState<Tab>('dashboard');
  const [state, setState] = React.useState<State>(EMPTY_STATE);
  const [previewText, setPreviewText] = React.useState('{"reason":"preview","patches":[]}');
  const [previewResult, setPreviewResult] = React.useState<StoryPatchPreviewResponse | null>(null);
  const [contractText, setContractText] = React.useState('');
  const [contractResult, setContractResult] = React.useState<StoryContractPreviewResponse | null>(null);
  const [promptText, setPromptText] = React.useState<string>(ko.storyDev.defaultPromptReplayJson);
  const [promptResult, setPromptResult] = React.useState<StoryPromptReplayResponse | null>(null);

  const load = React.useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const [timeline, debt, graph, contract] = await Promise.all([
        getStoryPatchTimeline(gameId),
        getStoryDebt(gameId),
        getStoryGraph(gameId),
        getStoryContract(gameId),
      ]);
      setState({
        loading: false,
        error: null,
        entries: timeline.entries,
        debt: debt.debt,
        graph: graph.graph,
        contract: contract.contract,
      });
      setContractText(JSON.stringify(contract.contract, null, 2));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  }, [gameId]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const rollbackLatest = async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      await rollbackStoryPatch(gameId);
      await load();
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  };

  const preview = async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    setPreviewResult(null);
    try {
      const proposal = JSON.parse(previewText) as { reason: string; patches: Record<string, unknown>[] };
      const result = await previewStoryPatch(gameId, proposal);
      setPreviewResult(result);
      setState((prev) => ({ ...prev, loading: false, error: null }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  };

  const previewContract = async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    setContractResult(null);
    try {
      const contract = JSON.parse(contractText) as Record<string, unknown>;
      const result = await previewStoryContract(gameId, contract);
      setContractResult(result);
      setState((prev) => ({ ...prev, loading: false, error: null }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  };

  const applyContract = async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    setContractResult(null);
    try {
      const contract = JSON.parse(contractText) as Record<string, unknown>;
      const result = await updateStoryContract(gameId, contract);
      setContractText(JSON.stringify(result.contract, null, 2));
      await load();
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  };

  const replayPrompt = async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    setPromptResult(null);
    try {
      const body = JSON.parse(promptText) as StoryPromptReplayRequest;
      const result = await replayStoryPrompt(gameId, body);
      setPromptResult(result);
      setState((prev) => ({ ...prev, loading: false, error: null }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  };

  return (
    <View className="absolute inset-x-5 top-14 z-30" style={{ height: '50%' }}>
      <Surface variant="floating" className="flex-1 overflow-hidden">
        <View className="flex-1 gap-3 p-3">
          <View className="flex-row items-center gap-2">
            <Text className="flex-1 font-sans-semibold text-panel text-fg-default" numberOfLines={1}>
              {ko.storyDev.title}
            </Text>
            <Chip variant="action" label={ko.storyDev.refresh} onPress={load} disabled={state.loading} />
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={ko.storyDev.close}
              onPress={onClose}
              className="h-7 w-7 items-center justify-center rounded-sm border border-border-default active:bg-canvas-inset"
            >
              <Text className="font-mono text-caption text-fg-muted">X</Text>
            </Pressable>
          </View>

          <View className="flex-row flex-wrap gap-2">
            {STORY_DEV_TABS.map((item) => (
              <StoryDevTab
                key={item.id}
                label={item.label}
                active={tab === item.id}
                onPress={() => setTab(item.id)}
              />
            ))}
          </View>

          {state.error ? (
            <Text className="font-sans text-caption text-danger-fg">{state.error}</Text>
          ) : null}

          <ScrollView
            className="flex-1"
            showsVerticalScrollIndicator={false}
            contentContainerStyle={isActionEditorTab(tab) ? { flexGrow: 1 } : undefined}
          >
            {tab === 'dashboard' ? (
              <Dashboard
                gameId={gameId}
                entries={state.entries}
                debt={state.debt}
                graph={state.graph}
                loading={state.loading}
              />
            ) : tab === 'graph' ? (
              <GraphInspector graph={state.graph} loading={state.loading} />
            ) : tab === 'timeline' ? (
              <Timeline entries={state.entries} loading={state.loading} onRollback={rollbackLatest} />
            ) : tab === 'debt' ? (
              <Debt debt={state.debt} loading={state.loading} />
            ) : tab === 'contract' ? (
              <ContractEditor
                text={contractText}
                setText={setContractText}
                result={contractResult}
                loading={state.loading}
                onPreview={previewContract}
                onApply={applyContract}
              />
            ) : tab === 'prompt' ? (
              <PromptReplay
                text={promptText}
                setText={setPromptText}
                result={promptResult}
                loading={state.loading}
                onReplay={replayPrompt}
              />
            ) : (
              <Preview
                text={previewText}
                setText={setPreviewText}
                result={previewResult}
                loading={state.loading}
                onPreview={preview}
              />
            )}
          </ScrollView>
        </View>
      </Surface>
    </View>
  );
}

function StoryDevTab({ label, active, onPress }: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  const bg = active ? 'bg-accent-muted border-accent-fg' : 'bg-transparent border-border-default active:bg-canvas-subtle';
  const color = active ? 'text-fg-default' : 'text-fg-muted';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
      onPress={onPress}
      className={`h-8 items-center justify-center rounded-sm border px-3 ${bg}`}
      style={{ minWidth: 70 }}
    >
      <Text numberOfLines={1} className={`font-sans-semibold text-caption ${color}`}>
        {label}
      </Text>
    </Pressable>
  );
}

function isActionEditorTab(tab: Tab) {
  return tab === 'contract' || tab === 'prompt' || tab === 'preview';
}

function Dashboard({ gameId, entries, debt, graph, loading }: {
  gameId: string;
  entries: StoryPatchLedgerEntry[];
  debt: StoryDebt | null;
  graph: StoryGraph | null;
  loading: boolean;
}) {
  if (loading && entries.length === 0 && debt === null && graph === null) {
    return <Empty loading label={ko.storyDev.loading} />;
  }
  const last = entries[entries.length - 1] ?? null;
  const rejected = entries.filter((entry) => entry.status === 'rejected').length;
  const debtCount = debt
    ? debt.unresolvedClues.length
      + debt.orphanCharacters.length
      + debt.orphanItems.length
      + debt.danglingQuestBeats.length
    : 0;
  const rejectRate = entries.length > 0 ? Math.round((rejected / entries.length) * 100) : 0;
  return (
    <View className="gap-2">
      <DashboardRow label={ko.storyDev.gameId} value={gameId} />
      <DashboardRow label={ko.storyDev.patchCount} value={String(entries.length)} />
      <DashboardRow label={ko.storyDev.lastPatch} value={last ? last.status : '-'} />
      <DashboardRow label={ko.storyDev.rejectRate} value={`${rejectRate}%`} />
      <DashboardRow label={ko.storyDev.debtCount} value={String(debtCount)} />
      <DashboardRow label={ko.storyDev.graphSize} value={graph ? ko.storyDev.changed(
        Object.keys(graph.nodes).length,
        Object.keys(graph.edges).length,
      ) : '-'} />
    </View>
  );
}

function DashboardRow({ label, value }: { label: string; value: string }) {
  return (
    <View className="flex-row gap-2 border-b border-border-default pb-1">
      <Text className="w-28 font-sans-semibold text-caption text-fg-muted" numberOfLines={1}>
        {label}
      </Text>
      <Text className="flex-1 font-mono text-caption text-fg-default" numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

function GraphInspector({ graph, loading }: { graph: StoryGraph | null; loading: boolean }) {
  if (!graph) return <Empty loading={loading} label={ko.storyDev.noGraph} />;
  const nodes = Object.values(graph.nodes).sort((a, b) => a.id.localeCompare(b.id));
  return (
    <View className="gap-2">
      <DashboardRow
        label={ko.storyDev.graphSize}
        value={ko.storyDev.changed(nodes.length, Object.keys(graph.edges).length)}
      />
      {nodes.slice(0, 24).map((node) => (
        <View key={node.id} className="gap-0.5 border-b border-border-default pb-1">
          <View className="flex-row gap-2">
            <Text className="flex-1 font-mono text-caption text-fg-default" numberOfLines={1}>
              {node.id}
            </Text>
            <Text className="font-sans text-caption text-fg-muted" numberOfLines={1}>
              {node.type}
            </Text>
          </View>
          <Text className="font-sans text-caption text-fg-muted" numberOfLines={1}>
            {nodeLabel(node)}
          </Text>
        </View>
      ))}
    </View>
  );
}

function nodeLabel(node: StoryGraph['nodes'][string]): string {
  const properties = node.properties ?? {};
  const label = properties.name ?? properties.title ?? properties.summary ?? '';
  return typeof label === 'string' && label ? label : '-';
}

function Timeline({ entries, loading, onRollback }: {
  entries: StoryPatchLedgerEntry[];
  loading: boolean;
  onRollback: () => void;
}) {
  if (entries.length === 0) {
    return <Empty loading={loading} label={ko.storyDev.noTimeline} />;
  }
  return (
    <View className="gap-2">
      {entries.slice().reverse().map((entry, index) => (
        <View key={`${entry.turn}:${entry.status}:${index}`} className="gap-1 border-b border-border-default pb-2">
          <View className="flex-row items-center gap-2">
            <Text className="font-mono text-caption text-fg-muted">
              {ko.storyDev.turn(entry.turn)}
            </Text>
            <Text className="font-sans-semibold text-caption text-fg-default">
              {entry.status}
            </Text>
            <Text className="flex-1 font-sans text-caption text-fg-muted" numberOfLines={1}>
              {entry.intentKind}
            </Text>
          </View>
          <Text className="font-sans text-caption text-fg-default" numberOfLines={2}>
            {entry.reason}
          </Text>
          <Text className="font-sans text-caption text-fg-muted" numberOfLines={1}>
            {ko.storyDev.changed(entry.changedNodeIds.length, entry.changedEdgeIds.length)}
          </Text>
        </View>
      ))}
      <View className="items-start pt-1">
        <Chip
          variant="action"
          label={ko.storyDev.rollback}
          onPress={onRollback}
          disabled={loading || !entries.some(canRollbackEntry)}
        />
      </View>
    </View>
  );
}

function canRollbackEntry(entry: StoryPatchLedgerEntry): boolean {
  return (
    entry.status === 'accepted'
    && (entry.changedNodeIds.length > 0 || entry.changedEdgeIds.length > 0)
  );
}

function Debt({ debt, loading }: { debt: StoryDebt | null; loading: boolean }) {
  if (!debt) return <Empty loading={loading} label={ko.storyDev.noDebt} />;
  const groups = [
    [ko.storyDev.unresolvedClues, debt.unresolvedClues],
    [ko.storyDev.orphanCharacters, debt.orphanCharacters],
    [ko.storyDev.orphanItems, debt.orphanItems],
    [ko.storyDev.danglingQuestBeats, debt.danglingQuestBeats],
  ] as const;
  if (groups.every(([, entries]) => entries.length === 0)) {
    return <Empty loading={loading} label={ko.storyDev.noDebt} />;
  }
  return (
    <View className="gap-3">
      {groups.map(([title, entries]) => (
        entries.length > 0 ? (
          <DebtGroup key={title} title={title} entries={entries} />
        ) : null
      ))}
    </View>
  );
}

function DebtGroup({ title, entries }: { title: string; entries: StoryDebtEntry[] }) {
  return (
    <View className="gap-1">
      <Text className="font-sans-semibold text-caption text-fg-muted">{title}</Text>
      {entries.map((entry) => (
        <View key={entry.id} className="gap-0.5">
          <Text className="font-sans-semibold text-caption text-fg-default" numberOfLines={1}>
            {entry.title}
          </Text>
          <Text className="font-sans text-caption text-fg-muted" numberOfLines={2}>
            {entry.reason}
          </Text>
        </View>
      ))}
    </View>
  );
}

function Empty({ loading, label }: { loading: boolean; label: string }) {
  return (
    <Text className="font-sans text-caption text-fg-muted">
      {loading ? ko.storyDev.loading : label}
    </Text>
  );
}
