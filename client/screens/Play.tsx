import { useEffect, useState } from 'react';
import { Pressable, View } from 'react-native';

import { Buttons } from '@/components/game/Buttons';
import { ClarifyCard } from '@/components/game/ClarifyCard';
import { Clocks } from '@/components/game/Clocks';
import { CommandBar } from '@/components/game/CommandBar';
import { ConfirmCard } from '@/components/game/ConfirmCard';
import { CostCard } from '@/components/game/CostCard';
import { Ending } from '@/components/game/Ending';
import { GrowthCard } from '@/components/game/GrowthCard';
import { Header } from '@/components/game/Header';
import { LastRoll } from '@/components/game/LastRoll';
import { Narration } from '@/components/game/Narration';
import { Record } from '@/components/game/Record';
import { RollCard } from '@/components/game/RollCard';
import { Scene } from '@/components/game/Scene';
import { Self } from '@/components/game/Self';
import { ko } from '@/locale/ko';
import { frame as frameAt } from '@/logic/reveal';
import type { Game } from '@/logic/useGame';
import type { GameView, StepRecord } from '@/services/types';

function lastRolled(steps: StepRecord[] | undefined): StepRecord | null {
  return [...(steps ?? [])].reverse().find((s) => s.roll && s.result !== 'blocked') ?? null;
}

/** The play screen (ui.md 2.1): fixed rows, the narration takes what is left, cards rise over the rows. */
export function Play({ game }: { game: Game }) {
  const view = game.view as GameView;
  const { phase, reveal } = game;
  const [now, setNow] = useState(Date.now());
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
      <Header view={rows} />
      <Clocks clocks={rows.clocks} crisis={revealing ? [] : crisis} />
      {phase === 'ending' ? <Ending view={view} recaps={game.recaps} onNew={game.newGame} /> : (
        <View className="min-h-0 flex-1">
          <View className="min-h-0 flex-1">
            <Self player={rows.player} onGrowth={view.growth.length && game.growthLater ? game.openGrowth : undefined} />
            <Scene scene={rows.scene} />
            <Record journal={rows.journal} />
            <Narration narration={game.narration} hold={revealing} failed={phase === 'narration_error'}
              fallback={view.last ? '' : view.scene.place.senses.join(', ')}
              onTyped={game.typed} onRetry={game.retryNarration} />
            <LastRoll step={lastRolled(shownSteps)} />
            <Buttons buttons={view.buttons} disabled={phase !== 'idle'} onPress={(action) => game.command({ action })} />
            {card ? <View className="absolute bottom-0 left-0 right-0 top-0">{card}</View> : null}
            {revealing ? (
              <Pressable accessibilityLabel="skip" className="absolute bottom-0 left-0 right-0 top-0" onPress={game.skip} />
            ) : null}
          </View>
          <CommandBar mode={mode} sent={game.sent} notice={game.notice}
            placeholder={view.due.length ? ko.payFirst : ko.placeholder}
            onSend={(text) => game.command({ text })} onResend={game.resend} onNew={game.newGame} />
        </View>
      )}
    </View>
  );
}
