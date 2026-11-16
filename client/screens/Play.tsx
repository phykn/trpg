import { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';

import { ChatLog } from '@/components/game/ChatLog';
import { DiceSheet } from '@/components/game/DiceSheet';
import { ConcludeSheet, PickSheet, type Picks, type Question } from '@/components/game/ConcludeSheet';
import { InputBar } from '@/components/game/InputBar';
import { OffersRow } from '@/components/game/OffersRow';
import { MovesSheet } from '@/components/game/MovesSheet';
import { NotebookSheet } from '@/components/game/NotebookSheet';
import { PeopleRow } from '@/components/game/PeopleRow';
import { SettingsMenu } from '@/components/game/SettingsMenu';
import { TopBar } from '@/components/game/TopBar';
import { TopicCard, type Topic } from '@/components/game/TopicCard';
import { Resend } from '@/components/ui/Resend';
import { findAct, findLine } from '@/logic/notebook';
import type { Entry, Phase } from '@/logic/useGame';
import type { Act, CommandBody, GameView, Group, RollResult } from '@/services/types';

// Which sheet is open; the notebook may have one line unfolded.
type Open =
  | { kind: 'notebook'; group: Group; line?: number }
  | { kind: 'moves' }
  | { kind: 'conclude' }
  | { kind: 'pick'; question: Question }
  | { kind: 'topic'; topic: Topic }
  | { kind: 'settings' }
  // A roll: `from` is where the log stood when it was sent, so its result is the first roll after it.
  | { kind: 'dice'; act: Act & { roll: NonNullable<Act['roll']> }; from: number | null }
  | null;

export function Play({ view, log, outgoing, phase, send, onResend, onRetryText, onHome }: {
  view: GameView; log: Entry[]; outgoing: Entry | null; phase: Phase; send: (body: CommandBody) => void;
  onResend: () => void; onRetryText: () => void; onHome: () => void;
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
    const found = findAct(view, id);
    if (found?.roll) {   // dice are rolled by the player on their sheet
      setOpen({ kind: 'dice', act: { ...found, roll: found.roll }, from: null });
      return;
    }
    send(draft.trim() ? { do: id, text: draft.trim() } : { do: id });
    setDraft('');
    setOpen(null);
  }

  function roll() {
    if (open?.kind !== 'dice') return;
    send(draft.trim() ? { do: open.act.id, text: draft.trim() } : { do: open.act.id });
    setDraft('');
    setOpen({ ...open, from: log.length });
  }

  const dice = open?.kind === 'dice' ? open : null;
  const rolled = dice && dice.from !== null
    ? (log.slice(dice.from).find((e) => e.kind === 'roll') as RollResult | undefined) ?? null : null;
  // A roll that was refused or got no answer leaves no result: the sheet goes and the screen shows why.
  useEffect(() => {
    if (dice && dice.from !== null && !rolled && (phase === 'ready' || phase === 'stuck')) setOpen(null);
  }, [dice, rolled, phase]);

  // A sure action opens its dice once the answer is in (game/07 2절); closing leaves the button.
  const opened = useRef('');
  const now = playing && phase === 'ready' ? view.offers.find((o) => o.now && o.roll) : undefined;
  useEffect(() => {
    const key = `${view.revision}:${now?.id}`;
    if (!now?.roll || open || opened.current === key) return;
    opened.current = key;
    setOpen({ kind: 'dice', act: { ...now, roll: now.roll }, from: null });
  }, [now, open, view.revision]);

  // A line opens unfolded in its group; several lines open their group.
  function openLine(id: number | undefined, lines = id === undefined ? [] : [id]) {
    const first = lines.length ? findLine(view, lines[0]) : null;
    if (first) setOpen({ kind: 'notebook', group: first.group, line: lines.length === 1 ? lines[0] : undefined });
    else if (group) setOpen({ kind: 'notebook', group });
  }

  const openNotebook = () => setOpen({ kind: 'notebook', group: 'places' });

  return (
    <View className="min-h-0 flex-1">
      <TopBar view={view} onNotebook={openNotebook} onSettings={() => setOpen({ kind: 'settings' })} />
      <View className="min-h-0 flex-1">
        <ChatLog log={log} met={met} outgoing={outgoing} onNote={(lines) => openLine(undefined, lines)}
          onTopic={(topic) => setOpen({ kind: 'topic', topic })}
          waiting={phase === 'sending' || phase === 'streaming' ? phase : null} />
        {open?.kind === 'topic' ? <TopicCard topic={open.topic} met={met} onClose={() => setOpen(null)} /> : null}
      </View>
      <View className="border-t border-border-default">
        <PeopleRow people={view.people} met={met} look={playing ? view.place.look : null} locked={locked}
          onAct={(id) => send({ do: id })}
          onMoves={playing && view.place.moves.length ? () => setOpen({ kind: 'moves' }) : undefined} />
        <OffersRow offers={playing ? view.offers : []} locked={locked} onAct={act} />
        {phase === 'stuck' || phase === 'text_error' ? (
          <View className="px-3 py-2"><Resend onResend={phase === 'stuck' ? onResend : onRetryText} /></View>
        ) : (
          <InputBar partner={view.people.find((p) => p.partner)?.name ?? null} locked={locked} text={draft} onText={setDraft}
            onSend={(text) => { send({ text }); setDraft(''); }} />
        )}
      </View>
      {dice ? (
        <DiceSheet roll={dice.act.roll} result={rolled} locked={locked && dice.from === null}
          onRoll={roll} onClose={() => setOpen(null)} />
      ) : null}
      {open?.kind === 'settings' ? <SettingsMenu onNewGame={onHome} onClose={() => setOpen(null)} /> : null}
      {open?.kind === 'moves' ? (
        <MovesSheet moves={view.place.moves} locked={locked} onMove={act} onClose={() => setOpen(null)} />
      ) : null}
      {concluding ? (
        <ConcludeSheet view={view} picks={picks} locked={phase !== 'ready'} onSubmit={() => { send({ conclude: picks }); setOpen(null); }}
          onPick={(question) => setOpen({ kind: 'pick', question })} onClose={closing ? undefined : () => setOpen(null)}
          onNotebook={openNotebook} />
      ) : null}
      {open?.kind === 'pick' ? (
        <PickSheet view={view} question={open.question} chosen={picks[open.question]}
          onPick={(id) => { setPicks({ ...picks, [open.question]: id }); setOpen({ kind: 'conclude' }); }}
          onClose={() => setOpen((o) => (o?.kind === 'pick' ? { kind: 'conclude' } : o))} />
      ) : null}
      {group ? (
        <NotebookSheet view={view} group={group} line={open?.kind === 'notebook' ? open.line : undefined} locked={locked}
          onGroup={(g) => setOpen({ kind: 'notebook', group: g })} onLine={(id) => openLine(id)} onAct={act}
          onConclude={playing ? () => setOpen({ kind: 'conclude' }) : undefined} onClose={() => setOpen(null)} />
      ) : null}
    </View>
  );
}
