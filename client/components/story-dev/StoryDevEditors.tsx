import type React from 'react';
import { Text, TextInput, View } from 'react-native';

import { Chip } from '@/components/ui';
import { ko } from '@/locale/ko';
import type {
  StoryContractPreviewResponse,
  StoryPatchPreviewResponse,
  StoryPromptReplayResponse,
} from '@/services/wire';

function ActionEditorFrame({ editor, feedback, actions }: {
  editor: React.ReactNode;
  feedback?: React.ReactNode;
  actions: React.ReactNode;
}) {
  return (
    <View className="flex-1 gap-2">
      {editor}
      {feedback ?? null}
      {actions}
    </View>
  );
}

export function Preview({ text, setText, result, loading, onPreview }: {
  text: string;
  setText: (value: string) => void;
  result: StoryPatchPreviewResponse | null;
  loading: boolean;
  onPreview: () => void;
}) {
  return (
    <ActionEditorFrame
      editor={(
        <TextInput
          testID="story-dev-editor"
          value={text}
          onChangeText={setText}
          multiline
          autoCapitalize="none"
          autoCorrect={false}
          accessibilityLabel={ko.storyDev.previewInput}
          className="rounded-sm border border-border-default bg-canvas-inset px-2 py-2 font-mono text-caption text-fg-default"
          style={{ minHeight: 220, flex: 1 }}
          textAlignVertical="top"
        />
      )}
      feedback={result ? (
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
      actions={(
        <View className="items-start pt-1">
          <Chip
            variant="action"
            label={ko.storyDev.previewRun}
            onPress={onPreview}
            disabled={loading}
          />
        </View>
      )}
    />
  );
}

export function ContractEditor({ text, setText, result, loading, onPreview, onApply }: {
  text: string;
  setText: (value: string) => void;
  result: StoryContractPreviewResponse | null;
  loading: boolean;
  onPreview: () => void;
  onApply: () => void;
}) {
  return (
    <ActionEditorFrame
      editor={(
        <TextInput
          testID="story-dev-editor"
          value={text}
          onChangeText={setText}
          multiline
          autoCapitalize="none"
          autoCorrect={false}
          accessibilityLabel={ko.storyDev.contractInput}
          className="rounded-sm border border-border-default bg-canvas-inset px-2 py-2 font-mono text-caption text-fg-default"
          style={{ minHeight: 220, flex: 1 }}
          textAlignVertical="top"
        />
      )}
      feedback={result ? (
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
      actions={(
        <View className="flex-row gap-2 pt-1">
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
      )}
    />
  );
}

export function PromptReplay({ text, setText, result, loading, onReplay }: {
  text: string;
  setText: (value: string) => void;
  result: StoryPromptReplayResponse | null;
  loading: boolean;
  onReplay: () => void;
}) {
  return (
    <ActionEditorFrame
      editor={(
        <TextInput
          testID="story-dev-editor"
          value={text}
          onChangeText={setText}
          multiline
          autoCapitalize="none"
          autoCorrect={false}
          accessibilityLabel={ko.storyDev.promptInput}
          className="rounded-sm border border-border-default bg-canvas-inset px-2 py-2 font-mono text-caption text-fg-default"
          style={{ minHeight: 220, flex: 1 }}
          textAlignVertical="top"
        />
      )}
      feedback={result ? (
        <View className="gap-2">
          <PromptResultRow label={ko.storyDev.promptIntent} value={String(result.intent.kind ?? '-')} />
          <PromptBlock title={ko.storyDev.systemPrompt} text={result.system_prompt} />
          <PromptBlock title={ko.storyDev.userPayload} text={JSON.stringify(result.user_payload, null, 2)} />
        </View>
      ) : null}
      actions={(
        <View className="items-start pt-1">
          <Chip
            variant="action"
            label={ko.storyDev.promptRun}
            onPress={onReplay}
            disabled={loading || text.trim().length === 0}
          />
        </View>
      )}
    />
  );
}

function PromptResultRow({ label, value }: { label: string; value: string }) {
  return (
    <View className="flex-row items-start gap-2 border-b border-border-default pb-1">
      <Text className="w-24 font-sans text-caption text-fg-muted">{label}</Text>
      <Text className="flex-1 font-mono text-caption text-fg-default" selectable>
        {value}
      </Text>
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
