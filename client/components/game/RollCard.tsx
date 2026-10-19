import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Card, CardOption, GameView, Preview, StepRecord } from '@/services/types';
import type { Frame } from '@/logic/reveal';
import { Boxes } from './Boxes';
import { Chips, signed } from './Chips';
import { Dice } from './Dice';
import { NumberLine } from './NumberLine';
import { OddsBar } from './OddsBar';

function gainLine(target: string, p: Preview): string {
  const g = p.gain;
  if (g.kind === 'fill') return ko.gainFill(target, g.boxes, g.fit > 0);
  if (g.kind === 'tag') return ko.gainTag(g.remove);
  if (g.kind === 'favor') return g.effects.join(', ');
  return ko.gainTopic;
}

function StakeRow({ label, clock, weight, preview }: { label: string; clock: number; weight: string | null; preview: Preview }) {
  return (
    <View className="flex-row flex-wrap items-center gap-2">
      <Text className="w-14 font-sans-semibold text-panel text-fg-muted">{label}</Text>
      {preview.clock && clock ? (
        <View className="flex-row items-center gap-1">
          <Text className="font-sans text-panel text-fg-default">{preview.clock.name}</Text>
          <Boxes fill={preview.clock.fill} boxes={preview.clock.boxes} next={clock} />
        </View>
      ) : null}
      {weight ? <Text className="font-sans text-panel text-fg-default">{ko.pickWeight(ko.weight[weight])}</Text> : null}
    </View>
  );
}

/** The roll card (ui.md 4.2) and, once rolled, the reveal inside it (ui.md 4.5). */
export function RollCard({ card, bands, onRoll, onCancel, step, frame, rolling }: {
  card: Card; bands: GameView['bands'];
  onRoll: (pick: string) => void; onCancel: () => void;
  step?: StepRecord; frame?: Frame; rolling?: boolean;
}) {
  const [pick, setPick] = useState(card.selected ?? card.options[card.options.length - 1].id);
  const chosen = card.options.find((o) => o.id === pick) ?? card.options[card.options.length - 1];
  const p = chosen.preview as Preview;
  const target = card.plan.step?.target;
  const high = p.risk === 'high';
  const locked = rolling || !!step;
  const relyChip = (o: CardOption) => o.preview?.mods.find((m) => m.kind === 'help' && m.label === o.label);
  const fixed = p.mods.filter((m) => !(m.kind === 'help' && m.label === chosen.label));
  const fill = target?.fill ?? 0;
  const own = step ? step.changes.findIndex((c) => c.kind === 'fill' && c.id === target?.id) : -1;
  const gained = frame && own >= 0 ? frame.boxes[own] ?? 0 : 0;

  return (
    <View className="flex-1 gap-2 rounded-t-xl border bg-canvas-floating px-4 pb-3 pt-3"
      style={{ borderColor: high ? colors.danger.fg : colors.border.strong }}>
      {target ? (
        <View className="flex-row items-center gap-2">
          <Text className="font-sans-semibold text-title text-fg-default">{target.name}</Text>
          {target.boxes ? <Boxes fill={fill + gained} boxes={target.boxes} fit={0} size={10} /> : null}
        </View>
      ) : null}
      <Text className="font-sans text-body text-fg-default">“{card.echo.text}”</Text>
      {card.echo.slots.length ? (
        <View className="flex-row flex-wrap gap-1">
          {card.echo.slots.map((s) => (
            <Text key={s.slot} className="rounded-sm border border-border-default px-2 font-sans text-chip text-fg-muted">{s.label}</Text>
          ))}
        </View>
      ) : null}
      <View className="gap-1 border-t border-border-default pt-2">
        {high ? <Text className="font-sans-semibold text-panel text-danger-fg">{ko.highRisk}</Text> : null}
        <Text className="font-sans text-panel text-fg-muted">{ko.riskLine(ko.risk[p.risk])}</Text>
        <View className="flex-row gap-2">
          <Text className="w-14 font-sans-semibold text-panel text-fg-muted">{ko.result.success}</Text>
          <Text className="flex-1 font-sans text-panel text-fg-default">{gainLine(target?.name ?? '', p)}</Text>
        </View>
        <StakeRow label={ko.cost} clock={p.stakes.mixed.clock} weight={p.stakes.mixed.weight} preview={p} />
        <StakeRow label={ko.result.fail} clock={p.stakes.fail.clock} weight={p.stakes.fail.weight} preview={p} />
      </View>
      <View className="gap-2 border-t border-border-default pt-2">
        {step && frame ? (
          <Chips chips={step.mods} decisive={frame.decisive} shown={frame.chips} />
        ) : (
          <>
            <Chips chips={fixed} />
            <Text className="font-sans-semibold text-panel text-fg-muted">{ko.rely}</Text>
            <View className="flex-row flex-wrap" style={{ gap: 6 }}>
              {card.options.map((o) => {
                const chip = relyChip(o);
                const on = o.id === pick;
                return (
                  <Pressable key={o.id} accessibilityRole="radio" accessibilityState={{ selected: on, disabled: locked }}
                    disabled={locked} onPress={() => setPick(o.id)}
                    className={`rounded-md border px-2 py-1 ${on ? 'border-gold-fg bg-accent-muted' : 'border-border-default'}`}>
                    <Text className={`font-sans ${card.options.length > 6 ? 'text-chip' : 'text-panel'} ${on ? 'text-gold-fg' : 'text-fg-default'}`}>
                      {on ? '● ' : ''}{o.label}{chip ? ` ${signed(chip.value)}` : ''}{o.note ? ` · ${o.note}` : ''}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </>
        )}
        {step && frame ? <NumberLine bands={bands} point={frame.point} settled={frame.settled} /> : <OddsBar odds={p.odds} />}
        {frame?.settled ? (
          <Text className="font-sans-semibold text-title text-gold-fg">{ko.result[frame.settled]}</Text>
        ) : null}
      </View>
      <View className="mt-auto flex-row items-center justify-between border-t border-border-default pt-3">
        <Dice state={frame?.blocked ? 'gone' : step ? 'stopped' : rolling ? 'rolling' : 'ready'}
          values={frame ? frame.dice : [null, null]} label={ko.hold} onRelease={() => onRoll(pick)} />
        {!locked ? (
          <Pressable accessibilityRole="button" onPress={onCancel} className="rounded-md border border-border-default px-3 py-2">
            <Text className="font-sans text-panel text-fg-default">{ko.cancel}</Text>
          </Pressable>
        ) : null}
      </View>
      {frame?.blocked?.length ? (
        <Text className="font-sans-semibold text-title text-danger-fg">{frame.blocked.join(', ')}</Text>
      ) : null}
    </View>
  );
}
