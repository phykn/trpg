import { Text, View } from 'react-native';

import { colors, spacing } from '@/design/tokens';
import { ko } from '@/locale/ko';

import { RollResult } from './RollResult';
import type { LogEntry, NarrationCue } from '@/logic/log/types';

export function LogItem({ entry }: { entry: LogEntry }) {
  switch (entry.kind) {
    case 'gm':
      return <GMNarration entry={entry} />;
    case 'player':
      return <PlayerMessage text={entry.text} />;
    case 'act':
      return isCombatActSummary(entry.text) ? null : <ActMessage text={entry.text} />;
    case 'roll':
      return <RollResult entry={entry} />;
    default:
      // Server may add a new log kind ahead of a client deploy — render nothing
      // rather than letting FlatList trip on undefined.
      return null;
  }
}

type Segment = { text: string; kind: 'plain' | 'mark' | 'speech' };

function isCombatActSummary(text: string): boolean {
  return [
    '싸움의 중심을 잡습니다',
    '전투 행동을 이어갑니다',
    '전투에서 패배합니다',
    '전투를 끝냅니다',
    '교전권 밖으로 물러납니다',
    '전투선 밖으로 빠져나옵니다',
    '싸움을 멈춥니다',
    '전투가 끝납니다',
  ].some((phrase) => text.includes(phrase));
}

function splitDialogue(text: string): Segment[] {
  const re = /「([^」]*)」/g;
  const parts: Segment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push({ text: text.slice(last, m.index), kind: 'plain' });
    parts.push({ text: '「', kind: 'mark' });
    parts.push({ text: m[1], kind: 'speech' });
    parts.push({ text: '」', kind: 'mark' });
    last = re.lastIndex;
  }
  if (last < text.length) parts.push({ text: text.slice(last), kind: 'plain' });
  return parts;
}

function NarrationParts({ segments }: { segments: Segment[] }) {
  return (
    <>
      {segments.map((s, i) =>
        s.kind === 'mark' ? (
          <Text key={i} className="text-accent-fg">{s.text}</Text>
        ) : s.kind === 'speech' ? (
          <Text key={i} className="font-sans-medium">{s.text}</Text>
        ) : (
          s.text
        ),
      )}
    </>
  );
}

function gmTextClass(entry: Extract<LogEntry, { kind: 'gm' }>): string {
  if (entry.outcome === 'success') return 'text-success-fg';
  if (entry.outcome === 'failure') return 'text-danger-fg';
  return 'text-fg-default';
}

function cueToneClass(cue: NarrationCue): { box: string; text: string } {
  if (cue.kind === 'warning') return { box: 'border-danger-fg bg-canvas-subtle', text: 'text-danger-fg' };
  if (cue.kind === 'opportunity') return { box: 'border-success-fg bg-canvas-subtle', text: 'text-success-fg' };
  if (cue.kind === 'change') return { box: 'border-accent-fg bg-accent-muted', text: 'text-accent-fg' };
  return { box: 'border-border-default bg-canvas-inset', text: 'text-fg-muted' };
}

function NarrationCues({ cues }: { cues: NarrationCue[] }) {
  return (
    <View
      accessible
      accessibilityLabel={ko.cue.groupLabel}
      className="mt-3 gap-1.5"
    >
      {cues.map((cue, i) => {
        const toneClass = cueToneClass(cue);
        return (
          <View key={`${cue.kind}-${i}`} className={`rounded-sm border px-2.5 py-1.5 ${toneClass.box}`}>
            <Text className={`font-sans-semibold text-caption ${toneClass.text}`}>{cue.label}</Text>
            <Text className={`font-serif text-body ${toneClass.text}`}>{cue.text}</Text>
          </View>
        );
      })}
    </View>
  );
}

function GMNarration({ entry }: { entry: Extract<LogEntry, { kind: 'gm' }> }) {
  const paragraphs = entry.text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  const textClass = gmTextClass(entry);
  return (
    <View
      style={{
        borderLeftWidth: 2,
        borderLeftColor: colors.accent.fg,
        paddingLeft: spacing[3],
      }}
    >
      {paragraphs.map((p, i) => {
        return (
          <Text
            key={i}
            className={`font-serif text-narration ${textClass}`}
            style={{ marginTop: i === 0 ? 0 : spacing[3] }}
          >
            <NarrationParts segments={splitDialogue(p)} />
          </Text>
        );
      })}
      {entry.cues && entry.cues.length > 0 ? <NarrationCues cues={entry.cues} /> : null}
    </View>
  );
}

function PlayerMessage({ text }: { text: string }) {
  return (
    <View
      style={{
        borderLeftWidth: 2,
        borderLeftColor: colors.exp.fg,
        paddingLeft: spacing[3],
      }}
    >
      <Text className="font-serif text-lead text-accent-fg">
        {text}
      </Text>
    </View>
  );
}

function ActMessage({ text }: { text: string }) {
  return (
    <View
      style={{
        borderLeftWidth: 2,
        borderLeftColor: colors.fg.muted,
        paddingLeft: spacing[3],
      }}
    >
      <Text className="font-sans text-caption text-fg-muted">
        {text}
      </Text>
    </View>
  );
}
