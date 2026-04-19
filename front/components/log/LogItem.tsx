import type { LogEntry } from '@/types/game';
import { GMNarration } from './GMNarration';
import { PlayerMessage } from './PlayerMessage';
import { ActDivider } from './ActDivider';
import { RollResult } from './RollResult';

export function LogItem({ entry }: { entry: LogEntry }) {
  switch (entry.kind) {
    case 'gm':     return <GMNarration text={entry.text} />;
    case 'player': return <PlayerMessage text={entry.text} />;
    case 'act':    return <ActDivider text={entry.text} />;
    case 'roll':   return <RollResult entry={entry} />;
  }
}
