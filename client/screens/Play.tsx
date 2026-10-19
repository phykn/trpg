import { View } from 'react-native';

import { Choices } from '@/components/game/Choices';
import { CommandBar } from '@/components/game/CommandBar';
import { ConfirmCard } from '@/components/game/ConfirmCard';
import { Growth } from '@/components/game/Growth';
import { Meters } from '@/components/game/Meters';
import { Narration } from '@/components/game/Narration';
import { Button } from '@/components/ui/Button';
import { ko } from '@/locale/ko';
import type { Narration as NarrationState, Notice } from '@/logic/useGame';
import type { Command, GameView } from '@/services/types';

export function Play({ view, narration, notice, blocked, onSend, onRetry, onDismiss, onNew }: {
  view: GameView;
  narration: NarrationState;
  notice: Notice;
  blocked: boolean;
  onSend: (command: Command) => void;
  onRetry: () => void;
  onDismiss: () => void;
  onNew: () => void;
}) {
  const busy = blocked || narration.status === 'streaming';
  const pending = view.pending;
  let bottom;
  if (view.ending) bottom = <View className="border-t border-border-default px-6 py-3"><Button label={ko.newGame} primary onPress={onNew} /></View>;
  else if (pending?.kind === 'confirm' && pending.card) bottom = <ConfirmCard card={pending.card} disabled={busy} onSend={onSend} />;
  else if (pending?.kind === 'growth') {
    bottom = <Growth options={pending.options} disabled={busy} onPick={(id) => onSend({ action_id: id })} />;
  } else if (notice) {
    bottom = <Choices title={notice.reason} options={notice.options} disabled={busy} onPick={(id) => { onDismiss(); onSend({ action_id: id }); }}
      extra={{ label: ko.dismiss, onPress: onDismiss }} />;
  } else bottom = <CommandBar buttons={view.buttons} disabled={busy} onSend={onSend} />;
  return (
    <View className="flex-1 min-h-0">
      <Meters view={view} />
      <View className="flex-1 min-h-0 px-6 py-4">
        <Narration view={view} narration={narration} onRetry={onRetry} />
      </View>
      {bottom}
    </View>
  );
}
