import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { ChatLog } from '@/components/game/ChatLog';
import { ConcludeSheet, PickSheet, type Picks, type Question } from '@/components/game/ConcludeSheet';
import { InputBar } from '@/components/game/InputBar';
import { OffersRow } from '@/components/game/OffersRow';
import { MovesSheet } from '@/components/game/MovesSheet';
import { NotebookSheet } from '@/components/game/NotebookSheet';
import { Overlay } from '@/components/game/Overlay';
import { PeopleRow } from '@/components/game/PeopleRow';
import { TopBar } from '@/components/game/TopBar';
import { Resend } from '@/components/ui/Resend';
import { findLine } from '@/logic/notebook';
import type { Entry, Phase } from '@/logic/useGame';
import type { CommandBody, GameView, Group } from '@/services/types';

// Which sheet is open; the notebook may have one line unfolded.
type Open =
  | { kind: 'notebook'; group: Group; line?: number }
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
  const group = open?.kind === 'notebook' ? open.group : undefined;
  // With the turns spent the conclusion stays up whenever nothing else is open.
  const concluding = open?.kind === 'conclude' || open?.kind === 'pick' || (closing && !open && phase === 'ready');

  // Lines count as read once their group is on screen.
  const unread = group ? view.notebook[group].filter((l) => l.new).map((l) => l.id) : [];
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

  // A line opens unfolded in its group; several lines open their group.
  function openLine(id: number | undefined, lines = id === undefined ? [] : [id]) {
    const first = lines.length ? findLine(view, lines[0]) : null;
    if (first) setOpen({ kind: 'notebook', group: first.group, line: lines.length === 1 ? lines[0] : undefined });
    else if (group) setOpen({ kind: 'notebook', group });
  }

  const openNotebook = () => setOpen({ kind: 'notebook', group: 'places' });

  return (
    <View className="min-h-0 flex-1">
      <TopBar view={view} onPlace={playing && view.place.moves.length ? () => setOpen({ kind: 'moves' }) : undefined}
        onNotebook={openNotebook} />
      <ChatLog log={log} met={met} outgoing={outgoing} onNote={(lines) => openLine(undefined, lines)}
        waiting={phase === 'sending' || phase === 'streaming' ? phase : null} />
      <View className="border-t border-border-default">
        <PeopleRow people={view.people} met={met} look={playing ? view.place.look : null} locked={locked}
          onAct={(id) => send({ do: id })} />
        <OffersRow offers={playing ? view.offers : []} locked={locked} onAct={act} />
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
          <NotebookSheet view={view} group={group} line={open?.kind === 'notebook' ? open.line : undefined} locked={locked}
            onGroup={(g) => setOpen({ kind: 'notebook', group: g })} onLine={(id) => openLine(id)} onAct={act}
            onConclude={playing ? () => setOpen({ kind: 'conclude' }) : undefined} onClose={() => setOpen(null)} />
        </Overlay>
      ) : null}
    </View>
  );
}
