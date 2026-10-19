import { useEffect, useRef, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { motion, text as sizes } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { fitSize } from '@/logic/fit';
import type { Narration as N } from '@/logic/useGame';

export function Narration({ narration, hold, fallback, onTyped, onRetry, failed }: {
  narration: N; hold: boolean; fallback: string; onTyped: () => void; onRetry: () => void; failed: boolean;
}) {
  const [box, setBox] = useState({ width: 0, height: 0 });
  const [shown, setShown] = useState(0);
  const full = narration.text ?? '';
  const typedFor = useRef<string | null>(null);

  useEffect(() => {
    if (hold || !full) return undefined;
    setShown(0);
    const id = setInterval(() => setShown((n) => {
      if (n + 1 >= full.length) { clearInterval(id); return full.length; }
      return n + 1;
    }), 1000 / motion.typeRate);
    return () => clearInterval(id);
  }, [full, hold]);

  useEffect(() => {
    if (!hold && full && shown >= full.length && typedFor.current !== full) {
      typedFor.current = full;
      onTyped();
    }
  }, [shown, full, hold, onTyped]);

  const body = [full, narration.recap].filter(Boolean).join('\n\n') || (narration.text === null && !narration.stage ? fallback : '');
  const size = box.width ? fitSize(body, box.width, box.height, sizes.narration, sizes.lineHeight) : sizes.narration[0];
  const visible = hold ? '' : full.slice(0, shown);

  return (
    <Pressable accessibilityRole="text" className="min-h-0 flex-1 justify-end px-4 py-2" onPress={() => setShown(full.length)}
      onLayout={(e) => setBox({ width: e.nativeEvent.layout.width - 32, height: e.nativeEvent.layout.height - 16 })}>
      {narration.stage && !full ? (
        <Text accessibilityLiveRegion="polite" className="font-sans text-chip text-fg-subtle">{ko.stage[narration.stage]}</Text>
      ) : null}
      <Text className="font-sans text-fg-default" style={{ fontSize: size, lineHeight: size * sizes.lineHeight }}>
        {full ? visible : narration.text === null && !narration.stage && !failed ? fallback : ''}
      </Text>
      {narration.recap && !hold && shown >= full.length ? (
        <Text className="mt-3 font-sans text-fg-muted" style={{ fontSize: size, lineHeight: size * sizes.lineHeight }}>
          {narration.recap}
        </Text>
      ) : null}
      {failed ? (
        <View className="mt-2 gap-2">
          <Text accessibilityRole="alert" className="font-sans-semibold text-body text-danger-fg">{ko.narrationFailed}</Text>
          {narration.error ? <Text className="font-sans text-chip text-fg-subtle">{narration.error}</Text> : null}
          <Pressable accessibilityRole="button" onPress={onRetry} className="self-start rounded-md border border-border-default px-3 py-1">
            <Text className="font-sans text-panel text-fg-default">{ko.retryNarration}</Text>
          </Pressable>
        </View>
      ) : null}
    </Pressable>
  );
}
