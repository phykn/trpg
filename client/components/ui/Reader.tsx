import { useLayoutEffect, useRef, useState } from 'react';
import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import { pageAt, paginate, type TextPage } from '@/logic/paginate';
import { Button } from './Button';

type Props = {
  text: string;
  onDone?: () => void;
  doneLabel?: string;
  disabled?: boolean;
};

export function Reader({ text, onDone, doneLabel = ko.chooseAction, disabled }: Props) {
  const probe = useRef<Text>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [pages, setPages] = useState<TextPage[]>([]);
  const [offset, setOffset] = useState(0);
  const index = pages.length ? pageAt(pages, offset) : 0;
  const last = index === pages.length - 1;

  useLayoutEffect(() => {
    const node = probe.current as unknown as HTMLElement | null;
    if (!node || !size.width || !size.height) return;
    const next = paginate(text, (part) => {
      node.textContent = part;
      return node.getBoundingClientRect().height <= size.height - 2;
    });
    node.textContent = '';
    setPages(next);
  }, [text, size.width, size.height]);

  return (
    <View className="flex-1 min-h-0 gap-4">
      <View className="flex-1 min-h-0 overflow-hidden" testID="reader-area" onLayout={({ nativeEvent: { layout } }) => {
        setSize((old) => old.width === layout.width && old.height === layout.height ? old : { width: layout.width, height: layout.height });
      }}>
        <Text ref={probe} aria-hidden className="reader-text absolute left-0 right-0 top-0 font-sans text-lead opacity-0" style={{ pointerEvents: 'none' }} />
        <Text testID="reader-text" accessibilityLiveRegion="polite" className="reader-text font-sans text-lead text-fg-default">{pages[index]?.text ?? ''}</Text>
      </View>
      <View className="flex-row items-center gap-3 border-t border-border-default pt-4">
        <Button label={ko.previousPage} disabled={!pages.length || index === 0} onPress={() => setOffset(pages[index - 1].start)} />
        <Text accessibilityLabel={ko.pageNumber(index + 1, pages.length || 1)} className="flex-1 text-center font-mono text-caption text-fg-subtle">{String(index + 1).padStart(2, '0')} / {String(pages.length || 1).padStart(2, '0')}</Text>
        <Button label={last && onDone ? doneLabel : ko.nextPage} primary={!!onDone && last} disabled={!pages.length || (last && (!onDone || disabled))} onPress={() => {
          if (last) onDone?.();
          else setOffset(pages[index + 1].start);
        }} />
      </View>
    </View>
  );
}
