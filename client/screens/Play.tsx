import { View } from 'react-native';

import { ChatLog } from '@/components/game/ChatLog';
import { InputBar } from '@/components/game/InputBar';
import { PeopleRow } from '@/components/game/PeopleRow';
import { TopBar } from '@/components/game/TopBar';
import { Resend } from '@/components/ui/Notice';
import type { Entry, Phase } from '@/logic/useGame';
import type { GameView } from '@/services/types';

export function Play({ view, log, phase, onSend, onAct, onResend, onRetryText }: {
  view: GameView; log: Entry[]; phase: Phase; onSend: (text: string) => void; onAct: (act: string) => void;
  onResend: () => void; onRetryText: () => void;
}) {
  const locked = phase !== 'ready' || view.stage !== 'play';
  const partner = view.people.find((p) => p.partner)?.name ?? null;
  return (
    <View className="min-h-0 flex-1">
      <TopBar view={view} />
      <ChatLog log={log} />
      <View className="border-t border-border-default">
        <PeopleRow people={view.people} locked={locked} onFace={onAct} />
        {phase === 'stuck' || phase === 'text_error' ? (
          <View className="px-3 py-2"><Resend onResend={phase === 'stuck' ? onResend : onRetryText} /></View>
        ) : (
          <InputBar partner={partner} locked={locked} onSend={onSend} />
        )}
      </View>
    </View>
  );
}
