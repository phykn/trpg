import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { ChatLog } from '@/components/game/ChatLog';
import { ConcludeSheet, PickSheet, type Picks, type Question } from '@/components/game/ConcludeSheet';
import { InputBar } from '@/components/game/InputBar';
import { LineSheet } from '@/components/game/LineSheet';
import { MovesSheet } from '@/components/game/MovesSheet';
import { findLine, NotebookSheet } from '@/components/game/NotebookSheet';
import { Overlay } from '@/components/game/Overlay';
import { PeopleRow } from '@/components/game/PeopleRow';
import { TopBar } from '@/components/game/TopBar';
import { Resend } from '@/components/ui/Notice';
import type { Entry, Phase } from '@/logic/useGame';
import type { CommandBody, GameView, Group } from '@/services/types';

type Open =
  | { kind: 'notebook'; group: Group }
  | { kind: 'line'; id: number; group?: Group }
  | { kind: 'moves' }
  | { kind: 'conclude' }
  | { kind: 'pick'; question: Question }
  | null;

export function Play({ view, log, phase, send, onResend, onRetryText }: {
  view: GameView; log: Entry[]; phase: Phase; send: (body: CommandBody) => void; onResend: () => void;
  onRetryText: () => void;
}) {
  const [open, setOpen] = useState<Open>(null);
  const [draft, setDraft] = useState('');
  const [picks, setPicks] = useState<Picks>({ who: null, how: null, why: null });
  const playing = view.stage === 'play';
  const closing = view.stage === 'closing';
  const locked = phase !== 'ready' || !playing;
  const partner = view.people.find((p) => p.partner)?.name ?? null;
  const found = open?.kind === 'line' ? findLine(view, open.id) : null;
  const concluding = open?.kind === 'conclude' || open?.kind === 'pick' || (closing && !open && phase === 'ready');

  const unread = open?.kind === 'notebook' ? view.notebook[open.group].filter((l) => l.new).map((l) => l.id)
    : found?.[1].new ? [found[1].id] : [];
  const readable = phase === 'ready' && (playing || closing);
  useEffect(() => {
    if (readable && unread.length) send({ read: unread });
  }, [readable, unread.join(',')]);   // eslint-disable-line react-hooks/exhaustive-deps

  function act(id: string) {
    send(draft.trim() ? { do: id, text: draft.trim() } : { do: id });
    setDraft('');
    setOpen(null);
  }

  function submit() {
    send({ conclude: picks });
    setOpen(null);
  }

  function openNote(lines: number[]) {
    const first = lines.length ? findLine(view, lines[0]) : null;
    if (!first) return;
    setOpen(lines.length === 1 ? { kind: 'line', id: lines[0] } : { kind: 'notebook', group: first[0] });
  }

  const close = () => setOpen(open?.kind === 'line' && open.group ? { kind: 'notebook', group: open.group } : null);
  const notebookGroup = open?.kind === 'notebook' || open?.kind === 'line' ? open.group : undefined;

  return (
    <View className="min-h-0 flex-1">
      <TopBar view={view} onPlace={playing && view.place.moves.length ? () => setOpen({ kind: 'moves' }) : undefined}
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
      {concluding ? (
        <Overlay onClose={closing ? () => undefined : () => setOpen(null)}>
          <ConcludeSheet view={view} picks={picks} locked={phase !== 'ready'} onSubmit={submit}
            onPick={(question) => setOpen({ kind: 'pick', question })} onMore={closing ? undefined : () => setOpen(null)}
            onNotebook={() => setOpen({ kind: 'notebook', group: 'places' })} />
        </Overlay>
      ) : null}
      {open?.kind === 'pick' ? (
        <Overlay full onClose={() => setOpen({ kind: 'conclude' })}>
          <PickSheet view={view} question={open.question} chosen={picks[open.question]}
            onPick={(id) => { setPicks({ ...picks, [open.question]: id }); setOpen({ kind: 'conclude' }); }}
            onClose={() => setOpen({ kind: 'conclude' })} />
        </Overlay>
      ) : null}
      {notebookGroup ? (
        <Overlay full onClose={() => setOpen(null)}>
          <NotebookSheet view={view} group={notebookGroup} onGroup={(g) => setOpen({ kind: 'notebook', group: g })}
            onLine={(id) => setOpen({ kind: 'line', id, group: notebookGroup })}
            onConclude={playing ? () => setOpen({ kind: 'conclude' }) : undefined} onClose={() => setOpen(null)} />
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
