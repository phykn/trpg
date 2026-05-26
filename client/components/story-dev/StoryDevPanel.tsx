import React from 'react';
import { Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { Chip, Surface } from '@/components/ui';
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
    <View className="absolute inset-x-5 top-14 z-30">
      <Surface variant="floating" className="overflow-hidden">
        <View className="gap-3 p-3">
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

          <View className="flex-row gap-2">
            <Chip
              variant="tab"
              label={ko.storyDev.dashboard}
              active={tab === 'dashboard'}
              onPress={() => setTab('dashboard')}
            />
            <Chip
              variant="tab"
              label={ko.storyDev.timeline}
              active={tab === 'timeline'}
              onPress={() => setTab('timeline')}
            />
            <Chip
              variant="tab"
              label={ko.storyDev.graph}
              active={tab === 'graph'}
              onPress={() => setTab('graph')}
            />
            <Chip
              variant="tab"
              label={ko.storyDev.debt}
              active={tab === 'debt'}
              onPress={() => setTab('debt')}
            />
            <Chip
              variant="tab"
              label={ko.storyDev.contract}
              active={tab === 'contract'}
              onPress={() => setTab('contract')}
            />
            <Chip
              variant="tab"
              label={ko.storyDev.prompt}
              active={tab === 'prompt'}
              onPress={() => setTab('prompt')}
            />
            <Chip
              variant="tab"
              label={ko.storyDev.preview}
              active={tab === 'preview'}
              onPress={() => setTab('preview')}
            />
          </View>

          {state.error ? (
            <Text className="font-sans text-caption text-danger-fg">{state.error}</Text>
          ) : null}

          <ScrollView style={{ maxHeight: 280 }} showsVerticalScrollIndicator={false}>
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

function Preview({ text, setText, result, loading, onPreview }: {
  text: string;
  setText: (value: string) => void;
  result: StoryPatchPreviewResponse | null;
  loading: boolean;
  onPreview: () => void;
}) {
  return (
    <View className="gap-2">
      <TextInput
        value={text}
        onChangeText={setText}
        multiline
        autoCapitalize="none"
        autoCorrect={false}
        accessibilityLabel={ko.storyDev.previewInput}
        className="min-h-24 rounded-sm border border-border-default bg-canvas-inset px-2 py-2 font-mono text-caption text-fg-default"
        textAlignVertical="top"
      />
      <View className="items-start">
        <Chip
          variant="action"
          label={ko.storyDev.previewRun}
          onPress={onPreview}
          disabled={loading}
        />
      </View>
      {result ? (
        <View className="gap-1">
          <Text className={`font-sans-semibold text-caption ${result.ok ? 'text-success-fg' : 'text-danger-fg'}`}>
            {result.ok ? ko.storyDev.previewOk : ko.storyDev.previewRejected}
          </Text>
          {result.reasons.length > 0 ? (
            <Text className="font-sans text-caption text-fg-muted">
              {result.reasons.join(', ')}
            </Text>
          ) : (
            <Text className="font-sans text-caption text-fg-muted">
              {ko.storyDev.changed(result.changedNodeIds.length, result.changedEdgeIds.length)}
            </Text>
          )}
        </View>
      ) : null}
    </View>
  );
}

function ContractEditor({ text, setText, result, loading, onPreview, onApply }: {
  text: string;
  setText: (value: string) => void;
  result: StoryContractPreviewResponse | null;
  loading: boolean;
  onPreview: () => void;
  onApply: () => void;
}) {
  return (
    <View className="gap-2">
      <TextInput
        value={text}
        onChangeText={setText}
        multiline
        autoCapitalize="none"
        autoCorrect={false}
        accessibilityLabel={ko.storyDev.contractInput}
        className="min-h-36 rounded-sm border border-border-default bg-canvas-inset px-2 py-2 font-mono text-caption text-fg-default"
        textAlignVertical="top"
      />
      <View className="flex-row gap-2">
        <Chip
          variant="action"
          label={ko.storyDev.contractRun}
          onPress={onPreview}
          disabled={loading || text.trim().length === 0}
        />
        <Chip
          variant="action"
          label={ko.storyDev.contractApply}
          onPress={onApply}
          disabled={loading || text.trim().length === 0}
        />
      </View>
      {result ? (
        <View className="gap-1">
          <Text className={`font-sans-semibold text-caption ${result.ok ? 'text-success-fg' : 'text-danger-fg'}`}>
            {result.ok ? ko.storyDev.contractOk : ko.storyDev.contractRejected}
          </Text>
          {result.reasons.length > 0 ? (
            <Text className="font-sans text-caption text-fg-muted">
              {result.reasons.join(', ')}
            </Text>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

function PromptReplay({ text, setText, result, loading, onReplay }: {
  text: string;
  setText: (value: string) => void;
  result: StoryPromptReplayResponse | null;
  loading: boolean;
  onReplay: () => void;
}) {
  return (
    <View className="gap-2">
      <TextInput
        value={text}
        onChangeText={setText}
        multiline
        autoCapitalize="none"
        autoCorrect={false}
        accessibilityLabel={ko.storyDev.promptInput}
        className="min-h-24 rounded-sm border border-border-default bg-canvas-inset px-2 py-2 font-mono text-caption text-fg-default"
        textAlignVertical="top"
      />
      <View className="items-start">
        <Chip
          variant="action"
          label={ko.storyDev.promptRun}
          onPress={onReplay}
          disabled={loading || text.trim().length === 0}
        />
      </View>
      {result ? (
        <View className="gap-2">
          <DashboardRow label={ko.storyDev.promptIntent} value={String(result.intent.kind ?? '-')} />
          <PromptBlock title={ko.storyDev.systemPrompt} text={result.system_prompt} />
          <PromptBlock title={ko.storyDev.userPayload} text={JSON.stringify(result.user_payload, null, 2)} />
        </View>
      ) : null}
    </View>
  );
}

function PromptBlock({ title, text }: { title: string; text: string }) {
  return (
    <View className="gap-1">
      <Text className="font-sans-semibold text-caption text-fg-muted">{title}</Text>
      <Text className="font-mono text-caption text-fg-default" numberOfLines={8}>
        {text}
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
          disabled={loading || !entries.some((entry) => entry.status === 'accepted')}
        />
      </View>
    </View>
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
