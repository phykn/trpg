import { useEffect, useState } from 'react';
import { Pressable, View } from 'react-native';

import { ClarifyCard } from '@/components/game/ClarifyCard';
import { Clocks } from '@/components/game/Clocks';
import { CommandBar } from '@/components/game/CommandBar';
import { ConfirmCard } from '@/components/game/ConfirmCard';
import { CostCard } from '@/components/game/CostCard';
import { Ending } from '@/components/game/Ending';
import { GrowthCard } from '@/components/game/GrowthCard';
import { Header } from '@/components/game/Header';
import { Menu } from '@/components/game/Menu';
import { Chat } from '@/components/game/Narration';
import { RollCard } from '@/components/game/RollCard';
import { Scene } from '@/components/game/Scene';
import { ko } from '@/locale/ko';
import { frame as frameAt } from '@/logic/reveal';
import type { Game } from '@/logic/useGame';
import { useLog } from '@/logic/useLog';
import type { GameView, StepRecord } from '@/services/types';

function lastRolled(steps: StepRecord[] | undefined): StepRecord | null {
  return [...(steps ?? [])].reverse().find((s) => s.roll && s.result !== 'blocked') ?? null;
}

function hint(scene: GameView['scene']): string {
  const open = scene.obstacles.find((o) => o.fill < o.boxes);
  if (open) return ko.askObject(open.name);
  if (scene.people.length) return ko.askPerson(scene.people[0].name);
  if (scene.things.length) return ko.askObject(scene.things[0].name);
  return ko.placeholder;
}

export function Play({ game }: { game: Game }) {
  const view = game.view as GameView;
  const { phase, reveal } = game;
  const [now, setNow] = useState(Date.now());
  const [menu, setMenu] = useState(false);
  const [sheet, setSheet] = useState(false);
  const log = useLog(game.gameId, view.story.premise);
  const turnNo = view.last?.turn ?? null;
  const live = turnNo !== null && !log.has(`story:${turnNo}`);
  const rolled = lastRolled(view.last?.steps);
  const roll = rolled?.roll ? { d1: rolled.roll.d1, d2: rolled.roll.d2, total: rolled.total ?? rolled.roll.d1 + rolled.roll.d2, result: rolled.result } : null;
  const onTyped = () => {
    if (turnNo !== null) {
      const text = [game.narration.text, game.narration.recap].filter(Boolean).join('\n\n');
      log.add(...(roll ? [{ id: `roll:${turnNo}`, kind: 'roll' as const, ...roll }] : []),
        { id: `story:${turnNo}`, kind: 'story', text });
    }
    game.typed();
  };
  // A restored turn already in the log is not typed again, so it counts as typed once its text arrives.
  useEffect(() => { if (phase === 'narrating' && !live && game.narration.text) game.typed(); }, [phase, live, game.narration.text]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (phase !== 'idle' && phase !== 'card') { setMenu(false); setSheet(false); } }, [phase]);
  const revealing = phase === 'revealing' && reveal !== null && !reveal.skipped;
  useEffect(() => {
    if (!revealing) return undefined;
    const id = setInterval(() => setNow(Date.now()), 40);
    return () => clearInterval(id);
  }, [revealing]);

  const frame = revealing && reveal ? frameAt(reveal.beats, now - reveal.start) : null;
  const step = frame && reveal ? reveal.steps[frame.step] : undefined;
  const rows = game.before ?? view;
  const shownSteps = revealing && !frame?.folded ? game.before?.last?.steps : (reveal?.steps ?? view.last?.steps);
  const rollOpen = (phase === 'rolling' && view.card?.kind === 'roll')
    || (revealing && reveal?.card && step?.roll && !frame?.folded);
  const crisis = view.last?.steps.flatMap((s) => s.changes.filter((c) => c.kind === 'crisis').map((c) => c.id as string));

  const commandsOpen = phase === 'idle' || phase === 'card';
  const menuOpen = menu && commandsOpen;
  const sheetOpen = sheet && phase === 'idle';
  const growthLater = view.growth.length > 0 && game.growthLater;
  let card = null;
  if (rollOpen) {
    const c = phase === 'rolling' ? view.card : reveal?.card;
    if (c) {
      card = (
        <RollCard card={c} bands={view.bands} rolling={phase === 'rolling'} step={revealing ? step : undefined}
          frame={revealing ? frame ?? undefined : undefined}
          onRoll={(pick) => game.command({ card: c.id, pick })} onCancel={() => game.command({ card: c.id, cancel: true })} />
      );
    }
  } else if (phase === 'card') {
    const c = view.card;
    if (view.due.length) card = <CostCard due={view.due} onPick={(action) => game.command({ action })} />;
    else if (c?.kind === 'roll') {
      card = <RollCard key={c.id} card={c} bands={view.bands} onRoll={(pick) => game.command({ card: c.id, pick })}
        onCancel={() => game.command({ card: c.id, cancel: true })} />;
    } else if (c?.kind === 'clarify') {
      card = <ClarifyCard card={c} onPick={(pick) => game.command({ card: c.id, pick })}
        onCancel={() => game.command({ card: c.id, cancel: true })} />;
    } else if (c?.kind === 'confirm') {
      card = <ConfirmCard card={c} onPick={(pick) => game.command({ card: c.id, pick })}
        onCancel={() => game.command({ card: c.id, cancel: true })} />;
    } else if (view.growth.length) {
      card = <GrowthCard growth={view.growth} onPick={(action) => game.command({ action })} onLater={game.laterGrowth} />;
    }
  }

  const mode = phase === 'idle' || phase === 'card' ? 'open' : phase === 'sending' ? 'sending'
    : phase === 'stuck' ? 'stuck' : phase === 'blocked' ? 'blocked' : 'locked';

  return (
    <View className="min-h-0 flex-1">
      <Header view={rows} menu={menuOpen} onMenu={commandsOpen ? () => { setSheet(false); setMenu(!menu); } : undefined}
        hero={sheetOpen}
        onGrowth={growthLater ? () => { setSheet(false); game.openGrowth(); } : undefined} onHero={phase === 'idle' ? () => { setMenu(false); setSheet(!sheet); } : undefined} />
      {phase === 'ending' ? <Ending view={view} recaps={game.recaps} onNew={game.newGame} /> : (
        <View className="min-h-0 flex-1">
          <View className="min-h-0 flex-1">
            <Scene scene={rows.scene} />
            <Clocks clocks={rows.clocks} crisis={revealing ? [] : crisis} />
            <Chat entries={log.entries} live={live} roll={roll} waiting={phase === 'sending' || phase === 'revealing' || (phase === 'narrating' && live)}
              narration={game.narration} hold={revealing} failed={phase === 'narration_error'}
              onTyped={onTyped} onRetry={game.retryNarration} />
            {revealing ? (
              <Pressable accessibilityLabel="skip" className="absolute bottom-0 left-0 right-0 top-0" onPress={game.skip} />
            ) : null}
          </View>
          <CommandBar mode={mode} sent={game.sent} notice={game.notice}
            placeholder={view.due.length ? ko.payFirst : hint(view.scene)}
            onSend={(text) => { log.add({ id: `you:${Date.now()}`, kind: 'you', text }); game.command({ text }); }} onResend={game.resend} onNew={game.newGame} />
          {card ? <View className="absolute bottom-0 left-0 right-0 max-h-full">{card}</View> : null}
        </View>
      )}
      {sheetOpen ? (
        <Pressable accessibilityLabel={ko.closeMenu} className="absolute bottom-0 left-0 right-0 top-0 z-10" onPress={() => setSheet(false)} />
      ) : null}
      {menuOpen ? <Menu onClose={() => setMenu(false)} onTitle={() => { setMenu(false); game.toTitle(); }} /> : null}
    </View>
  );
}
