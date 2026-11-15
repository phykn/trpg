import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { ChatLog } from '@/components/game/ChatLog';
import { InputBar } from '@/components/game/InputBar';
import { LineSheet } from '@/components/game/LineSheet';
import { MovesSheet } from '@/components/game/MovesSheet';
import { GROUP_ORDER, NotebookSheet } from '@/components/game/NotebookSheet';
import { Overlay } from '@/components/game/Overlay';
import { PeopleRow } from '@/components/game/PeopleRow';
import { TopBar } from '@/components/game/TopBar';
import { Resend } from '@/components/ui/Notice';
import type { Entry, Phase } from '@/logic/useGame';
import type { CommandBody, GameView, Group, Line } from '@/services/types';

type Open = { kind: 'notebook'; group: Group } | { kind: 'line'; id: number; group?: Group } | { kind: 'moves' } | null;

function findLine(view: GameView, id: number): [Group, Line] | null {
  for (const g of GROUP_ORDER) {
    const line = view.notebook[g].find((l) => l.id === id);
    if (line) return [g, line];
  }
  return null;
}

export function Play({ view, log, phase, send, onResend, onRetryText }: {
  view: GameView; log: Entry[]; phase: Phase; send: (body: CommandBody) => void; onResend: () => void;
  onRetryText: () => void;
}) {
  const [open, setOpen] = useState<Open>(null);
  const [draft, setDraft] = useState('');
  const locked = phase !== 'ready' || view.stage !== 'play';
  const partner = view.people.find((p) => p.partner)?.name ?? null;
  const found = open?.kind === 'line' ? findLine(view, open.id) : null;

  const unread = open?.kind === 'notebook' ? view.notebook[open.group].filter((l) => l.new).map((l) => l.id)
    : found?.[1].new ? [found[1].id] : [];
  const readable = phase === 'ready' && (view.stage === 'play' || view.stage === 'closing');
  useEffect(() => {
    if (readable && unread.length) send({ read: unread });
  }, [readable, unread.join(',')]);   // eslint-disable-line react-hooks/exhaustive-deps

  function act(id: string) {
    send(draft.trim() ? { do: id, text: draft.trim() } : { do: id });
    setDraft('');
    setOpen(null);
  }

  function openNote(lines: number[]) {
    const first = lines.length ? findLine(view, lines[0]) : null;
    if (!first) return;
    setOpen(lines.length === 1 ? { kind: 'line', id: lines[0] } : { kind: 'notebook', group: first[0] });
  }

  const close = () => setOpen(open?.kind === 'line' && open.group ? { kind: 'notebook', group: open.group } : null);

  return (
    <View className="min-h-0 flex-1">
      <TopBar view={view} onPlace={view.place.moves.length ? () => setOpen({ kind: 'moves' }) : undefined}
        onNotebook={() => setOpen({ kind: 'notebook', group: 'places' })} />
      <ChatLog log={log} onNote={openNote} />
      <View className="border-t border-border-default">
        <PeopleRow people={view.people} locked={locked} onFace={(id) => send({ do: id })} />
        {phase === 'stuck' || phase === 'text_error' ? (
          <View className="px-3 py-2"><Resend onResend={phase === 'stuck' ? onResend : onRetryText} /></View>
        ) : (
          <InputBar partner={partner} locked={locked} text={draft} onText={setDraft}
            onSend={(text) => { send({ text }); setDraft(''); }} />
        )}
      </View>
      {open?.kind === 'moves' ? (
        <Overlay onClose={close}>
          <MovesSheet moves={view.place.moves} locked={locked} onMove={act} onClose={close} />
        </Overlay>
      ) : null}
      {open?.kind === 'notebook' || (open?.kind === 'line' && open.group) ? (
        <Overlay full onClose={() => setOpen(null)}>
          <NotebookSheet view={view} group={open.group!}
            onGroup={(g) => setOpen({ kind: 'notebook', group: g })}
            onLine={(id) => setOpen({ kind: 'line', id, group: open.group })}
            onClose={() => setOpen(null)} />
        </Overlay>
      ) : null}
      {found ? (
        <Overlay onClose={close}>
          <LineSheet line={found[1]} locked={locked} onAct={act} onClose={close} />
        </Overlay>
      ) : null}
    </View>
  );
}
