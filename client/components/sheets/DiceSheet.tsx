import { useEffect, useRef, useState } from 'react';
import { Animated, Platform, Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { DragSheet } from '@/components/ui/DragSheet';
import { text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { Roll, RollResult } from '@/services/types';
import { Die } from '@/components/dice/Die';
import { Need, signed, Sum, Verdict } from '@/components/dice/RollParts';

const native = Platform.OS !== 'web';
// The dice tumble at least this long even when the answer is quick, then land one after the other.
const TUMBLE = 900;
const STAGGER = 180;
const SETTLE = 420;   // from the second die landing to the verdict
const LINGER = 1800;   // the verdict stays this long before the sheet slides away

type Stage = 'ready' | 'rolling' | 'landing' | 'landed' | 'done';

// The server decides the eyes when the roll is sent (game/05 3절); the dice tumble until they come and land on them.
export function DiceSheet({ roll, result, locked, onRoll, onClose }: {
  roll: Roll; result: RollResult | null; locked: boolean; onRoll: () => void; onClose: () => void;
}) {
  const [stage, setStage] = useState<Stage>('ready');
  const [first, setFirst] = useState(false);
  const started = useRef(0);
  const stamp = useRef(new Animated.Value(0)).current;

  // The log is rebuilt as the answer streams in, so the result comes again and again; only its arrival counts, and
  // the landing is timed once from then on.
  const arrived = result !== null;
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => {
    if (!arrived || !started.current || timers.current.length) return;
    const wait = Math.max(0, started.current + TUMBLE - Date.now());
    timers.current = [
      setTimeout(() => setFirst(true), wait),
      setTimeout(() => setStage('landing'), wait + STAGGER),
      setTimeout(() => {
        setStage('landed');
        Animated.spring(stamp, { toValue: 1, friction: 5, tension: 140, useNativeDriver: native }).start();
      }, wait + STAGGER + SETTLE),
      setTimeout(() => setStage('done'), wait + STAGGER + SETTLE + LINGER),
    ];
  }, [arrived, stamp]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  function start() {
    started.current = Date.now();
    setStage('rolling');
    onRoll();
  }

  const eyes = result?.eyes ?? [6, 6];
  const tumbling = stage === 'rolling';
  const shown = result && (stage === 'landed' || stage === 'done');
  return (
    <DragSheet fit title={roll.title} shut={stage === 'done'}
      onClose={stage === 'ready' || shown ? onClose : undefined}>
      {roll.aim ? <Text numberOfLines={3} className={text({ kind: 'scene' }, 'text-fg-muted')}>{roll.aim}</Text> : null}
      <View className="items-center gap-2 pt-1">
        <Need need={roll.need} large />
        <View className="flex-row flex-wrap justify-center gap-x-3">
          {roll.adds.map((a) => <Text key={a.name} className={text({ kind: 'sub' })}>{a.name} {signed(a.value)}</Text>)}
          <Text className={text({ kind: 'sub' }, 'font-sans-semibold')}>{ko.chance(roll.chance)}</Text>
          <Text className={text({ kind: 'sub' })}>{ko.cells(1)}</Text>
        </View>
      </View>
      <View className="h-20 flex-row items-center justify-center gap-6">
        <Die face={eyes[0]} rolling={tumbling && !first} spin={1} />
        <Die face={eyes[1]} rolling={tumbling} spin={-1} />
      </View>
      <View className="h-12 items-center justify-center">
        {shown ? (
          <Animated.View style={{ opacity: stamp, transform: [{ scale: stamp.interpolate({ inputRange: [0, 1], outputRange: [1.8, 1] }) }] }}>
            <View className="flex-row items-center gap-4">
              <Sum result={result} large />
              <Verdict won={result.won} large />
            </View>
          </Animated.View>
        ) : null}
      </View>
      {shown ? <Button tone="secondary" label={ko.close} onPress={() => setStage('done')} /> : (
        <Button icon="dice" label={ko.roll} disabled={stage !== 'ready' || locked} onPress={start} />
      )}
    </DragSheet>
  );
}
