import { useEffect, useRef, useState } from 'react';
import { Pressable, type TextInput, View } from 'react-native';

import { ClarifyCard } from '@/components/game/ClarifyCard';
import { Clocks } from '@/components/game/Clocks';
import { CommandBar } from '@/components/game/CommandBar';
import { ConfirmCard } from '@/components/game/ConfirmCard';
import { Ending } from '@/components/game/Ending';
import { GrowthCard } from '@/components/game/GrowthCard';
import { Header } from '@/components/game/Header';
import { Menu } from '@/components/game/Menu';
import { MoveCard } from '@/components/game/MoveCard';
import { Chat } from '@/components/game/Narration';
import { RollCard } from '@/components/game/RollCard';
import { Scene } from '@/components/game/Scene';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { frame as frameAt, rolled as isRolled, told } from '@/logic/reveal';
import type { Game } from '@/logic/useGame';
import { useLog } from '@/logic/useLog';
import type { GameView } from '@/services/types';

export function Play({ game }: { game: Game }) {
  const view = game.view as GameView;
  const { phase, reveal } = game;
  const [now, setNow] = useState(Date.now());
  const [menu, setMenu] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [draft, setDraft] = useState('');
  const input = useRef<TextInput>(null);
  const log = useLog(game.gameId, view.story.premise);
  const turnNo = view.last?.turn ?? null;
  const live = turnNo !== null && !log.has(`story:${turnNo}`);
  const rolled = [...(view.last?.steps ?? [])].reverse().find(isRolled);
  const roll = rolled ? {
    d1: rolled.roll.d1, d2: rolled.roll.d2, total: rolled.total ?? rolled.roll.d1 + rolled.roll.d2, result: rolled.result,
    dc: rolled.dc ?? 0, approach: rolled.mods.find((m) => m.kind === 'stat')?.label ?? '',
  } : null;
  const onTyped = () => {
    // A recap still to come would be lost once the turn is logged, so the turn waits for it to be typed too.
    if (turnNo !== null && !game.recapDue) {
      const text = told(game.narration);
      log.add(...(roll ? [{ id: `roll:${turnNo}`, kind: 'roll' as const, ...roll }] : []),
        { id: `story:${turnNo}`, kind: 'story', text });
    }
    game.typed();
  };
  // A restored turn already in the log is not typed again, so it counts as typed once its text arrives.
  useEffect(() => { if (phase === 'narrating' && !live && game.narration.text) game.typed(); }, [phase, live, game.narration.text, game.narration.recap]); // eslint-disable-line react-hooks/exhaustive-deps
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
  const rollOpen = ((phase === 'rolling' || game.lostRoll) && view.card?.kind === 'roll')
    || (revealing && reveal?.card && step?.roll && !frame?.folded);
  const crisis = view.last?.steps.flatMap((s) => s.changes.filter((c) => c.kind === 'crisis').map((c) => c.id as string));

  const commandsOpen = phase === 'idle' || phase === 'card';
  const menuOpen = menu && commandsOpen;
  const sheetOpen = sheet && phase === 'idle';
  const growthLater = view.growth.length > 0 && game.growthLater;
  const shown = rollOpen ? (revealing ? reveal?.card : view.card) : phase === 'card' ? view.card : null;
  const pick = (id: string) => { if (shown) game.command({ card: shown.id, pick: id }); };
  const cancel = () => { if (shown) game.command({ card: shown.id, cancel: true }); };
  let card = null;
  let roller = null;
  if (shown?.kind === 'roll') {
    // The same key as the open card's, so the card the player rolled stays as it was through to the reveal.
    roller = (
      <RollCard key={shown.id} card={shown} notice={phase === 'card' ? game.notice : undefined} rolling={phase === 'rolling'}
        step={revealing ? step : undefined} frame={revealing ? frame ?? undefined : undefined}
        onResend={game.lostRoll ? game.resend : undefined} onRoll={pick} onCancel={cancel} />
    );
  } else if (shown?.kind === 'clarify') card = <ClarifyCard card={shown} onPick={pick} onCancel={cancel} />;
  else if (shown?.kind === 'confirm') card = <ConfirmCard card={shown} onPick={pick} onCancel={cancel} />;
  else if (shown?.kind === 'move') card = <MoveCard card={shown} onPick={pick} onCancel={cancel} />;
  else if (phase === 'card' && view.growth.length) {
    card = <GrowthCard growth={view.growth} onPick={(action) => game.command({ action })} onLater={game.laterGrowth} />;
  }

  const mode = commandsOpen ? 'open' : phase === 'sending' ? 'sending' : phase === 'stuck' && !roller ? 'stuck' : 'locked';

  return (
    <View className="min-h-0 flex-1">
      <Header view={rows} menu={menuOpen} onMenu={commandsOpen ? () => { setSheet(false); setMenu(!menu); } : undefined}
        hero={sheetOpen}
        onGrowth={growthLater ? () => { setSheet(false); game.openGrowth(); } : undefined} onHero={phase === 'idle' ? () => { setMenu(false); setSheet(!sheet); } : undefined} />
      {phase === 'ending' ? <Ending view={view} recaps={game.recaps} onNew={game.newGame} /> : (
        <View className="min-h-0 flex-1">
          <View className="min-h-0 flex-1">
            <Clocks clocks={rows.clocks} crisis={revealing ? [] : crisis}
              time={rows.player.beats_max ? rows.player.beats / rows.player.beats_max : 0} />
            <Scene scene={rows.scene} onDraft={commandsOpen ? (t) => { setDraft(t); input.current?.focus(); } : undefined} />
            <Chat entries={log.entries} live={live} roll={roll} waiting={phase === 'sending' || phase === 'revealing' || (phase === 'narrating' && live)}
              narration={game.narration} hold={revealing} failed={phase === 'narration_error'}
              onTyped={onTyped} onRetry={game.retryNarration} />
            {revealing ? (
              <Pressable accessibilityLabel={ko.skip} className="absolute bottom-0 left-0 right-0 top-0" onPress={game.skip} />
            ) : null}
          </View>
          <CommandBar mode={mode} sent={game.sent} notice={roller ? null : game.notice} text={draft} onText={setDraft} inputRef={input}
            onSend={(text) => { log.add({ id: `you:${Date.now()}`, kind: 'you', text }); game.command({ text }); }} onResend={game.resend} />
          {card ? <View className="absolute bottom-0 left-0 right-0 max-h-full">{card}</View> : null}
        </View>
      )}
      {roller ? (
        <Pressable accessible={false} disabled={!revealing} onPress={game.skip}
          className="absolute bottom-0 left-0 right-0 top-0 z-30 justify-center px-4" style={{ backgroundColor: colors.overlay }}>
          {roller}
        </Pressable>
      ) : null}
      {sheetOpen ? (
        <Pressable accessibilityLabel={ko.close} className="absolute bottom-0 left-0 right-0 top-0 z-10" onPress={() => setSheet(false)} />
      ) : null}
      {menuOpen ? <Menu onClose={() => setMenu(false)} onTitle={() => { setMenu(false); game.toTitle(); }} /> : null}
    </View>
  );
}
