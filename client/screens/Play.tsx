import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { ChatLog } from '@/components/game/ChatLog';
import { ConcludeSheet, PickSheet, type Picks, type Question } from '@/components/game/ConcludeSheet';
import { InputBar } from '@/components/game/InputBar';
import { LineSheet } from '@/components/game/LineSheet';
import { MovesSheet } from '@/components/game/MovesSheet';
import { NotebookSheet } from '@/components/game/NotebookSheet';
import { Overlay } from '@/components/game/Overlay';
import { PeopleRow } from '@/components/game/PeopleRow';
import { TopBar } from '@/components/game/TopBar';
import { Resend } from '@/components/ui/Resend';
import { findLine } from '@/logic/notebook';
import type { Entry, Phase } from '@/logic/useGame';
import type { CommandBody, GameView, Group } from '@/services/types';

// Which sheet is open; a line opened from the notebook remembers its group, so closing it goes back there.
type Open =
  | { kind: 'notebook'; group: Group }
  | { kind: 'line'; id: number; group?: Group }
  | { kind: 'moves' }
  | { kind: 'conclude' }
  | { kind: 'pick'; question: Question }
  | null;

export function Play({ view, log, outgoing, phase, send, onResend, onRetryText }: {
  view: GameView; log: Entry[]; outgoing: Entry | null; phase: Phase; send: (body: CommandBody) => void;
  onResend: () => void; onRetryText: () => void;
}) {
  const [open, setOpen] = useState<Open>(null);
  const [draft, setDraft] = useState('');
  const [picks, setPicks] = useState<Picks>({ who: null, how: null, why: null });
  const playing = view.stage === 'play';
  const closing = view.stage === 'closing';
  const locked = phase !== 'ready' || !playing;
  const met = view.notebook.people.map((l) => l.text);
  const found = open?.kind === 'line' ? findLine(view, open.id) : null;
  const group = open?.kind === 'notebook' || open?.kind === 'line' ? open.group : undefined;
  // With the turns spent the conclusion stays up whenever nothing else is open.
  const concluding = open?.kind === 'conclude' || open?.kind === 'pick' || (closing && !open && phase === 'ready');

  // Lines count as read once their group or the line itself is on screen.
  const unread = open?.kind === 'notebook' ? view.notebook[open.group].filter((l) => l.new).map((l) => l.id)
    : found?.line.new ? [found.line.id] : [];
  const readable = phase === 'ready' && (playing || closing);
  useEffect(() => {
    if (readable && unread.length) send({ read: unread });
  }, [readable, unread.join(',')]);   // eslint-disable-line react-hooks/exhaustive-deps

  // What is typed in the box goes along with an act, as what the player says while doing it.
  function act(id: string) {
    send(draft.trim() ? { do: id, text: draft.trim() } : { do: id });
    setDraft('');
    setOpen(null);
  }

  function openNote(lines: number[]) {
    const first = lines.length ? findLine(view, lines[0]) : null;
    if (first) setOpen(lines.length === 1 ? { kind: 'line', id: lines[0] } : { kind: 'notebook', group: first.group });
  }

  const closeLine = () => setOpen(open?.kind === 'line' && open.group ? { kind: 'notebook', group: open.group } : null);
  const openNotebook = () => setOpen({ kind: 'notebook', group: 'places' });

  return (
    <View className="min-h-0 flex-1">
      <TopBar view={view} onPlace={playing && view.place.moves.length ? () => setOpen({ kind: 'moves' }) : undefined}
        onNotebook={openNotebook} />
      <ChatLog log={log} met={met} outgoing={outgoing} onNote={openNote}
        waiting={phase === 'sending' || phase === 'streaming' ? phase : null} />
      <View className="border-t border-border-default">
        <PeopleRow people={view.people} met={met} look={playing ? view.place.look : null} locked={locked}
          onAct={(id) => send({ do: id })} />
        {phase === 'stuck' || phase === 'text_error' ? (
          <View className="px-3 py-2"><Resend onResend={phase === 'stuck' ? onResend : onRetryText} /></View>
        ) : (
          <InputBar partner={view.people.find((p) => p.partner)?.name ?? null} locked={locked} text={draft} onText={setDraft}
            onSend={(text) => { send({ text }); setDraft(''); }} />
        )}
      </View>
      {open?.kind === 'moves' ? (
        <Overlay onClose={() => setOpen(null)}>
          <MovesSheet moves={view.place.moves} locked={locked} onMove={act} onClose={() => setOpen(null)} />
        </Overlay>
      ) : null}
      {concluding ? (
        <Overlay onClose={closing ? () => undefined : () => setOpen(null)}>
          <ConcludeSheet view={view} picks={picks} locked={phase !== 'ready'} onSubmit={() => { send({ conclude: picks }); setOpen(null); }}
            onPick={(question) => setOpen({ kind: 'pick', question })} onMore={closing ? undefined : () => setOpen(null)}
            onNotebook={openNotebook} />
        </Overlay>
      ) : null}
      {open?.kind === 'pick' ? (
        <Overlay full onClose={() => setOpen({ kind: 'conclude' })}>
          <PickSheet view={view} question={open.question} chosen={picks[open.question]}
            onPick={(id) => { setPicks({ ...picks, [open.question]: id }); setOpen({ kind: 'conclude' }); }}
            onClose={() => setOpen({ kind: 'conclude' })} />
        </Overlay>
      ) : null}
      {group ? (
        <Overlay full onClose={() => setOpen(null)}>
          <NotebookSheet view={view} group={group} onGroup={(g) => setOpen({ kind: 'notebook', group: g })}
            onLine={(id) => setOpen({ kind: 'line', id, group })}
            onConclude={playing ? () => setOpen({ kind: 'conclude' }) : undefined} onClose={() => setOpen(null)} />
        </Overlay>
      ) : null}
      {found ? (
        <Overlay onClose={closeLine}>
          <LineSheet line={found.line} about={found.line.about.flatMap((id) => findLine(view, id)?.line ?? [])} locked={locked}
            onAct={act} onLine={(id) => setOpen({ kind: 'line', id, group })} onClose={closeLine} />
        </Overlay>
      ) : null}
    </View>
  );
}
