import { Text, View } from 'react-native';

import { Chip } from '@/components/ui';
import { ko } from '@/locale/ko';
import type {
  StoryDebt,
  StoryDebtEntry,
  StoryGraph,
  StoryPatchLedgerEntry,
} from '@/services/wire';

export function Dashboard({ gameId, entries, debt, graph, loading }: {
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

export function GraphInspector({ graph, loading }: {
  graph: StoryGraph | null;
  loading: boolean;
}) {
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

export function Timeline({ entries, loading, onRollback }: {
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

export function Debt({ debt, loading }: {
  debt: StoryDebt | null;
  loading: boolean;
}) {
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

function nodeLabel(node: StoryGraph['nodes'][string]): string {
  const properties = node.properties ?? {};
  const label = properties.name ?? properties.title ?? properties.summary ?? '';
  return typeof label === 'string' && label ? label : '-';
}

function canRollbackEntry(entry: StoryPatchLedgerEntry): boolean {
  return (
    entry.status === 'accepted'
    && (entry.changedNodeIds.length > 0 || entry.changedEdgeIds.length > 0)
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
