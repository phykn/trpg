import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { layout, spacing } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { Button } from './Button';

export type ListEntry = { id: string; label: string; meta?: string; muted?: boolean };

export function PagedList({ entries, onSelect, disabled, empty = ko.noEntries }: {
  entries: ListEntry[];
  onSelect: (id: string) => void;
  disabled?: boolean;
  empty?: string;
}) {
  const [height, setHeight] = useState(0);
  const [offset, setOffset] = useState(0);
  const compact = height > 0 && height < layout.listRow;
  const rowHeight = height > 0 ? Math.min(layout.listRow, height) : layout.listRow;
  const count = Math.max(1, Math.min(3, Math.floor((height + spacing[3]) / (layout.listRow + spacing[3]))));
  const total = Math.max(1, Math.ceil(entries.length / count));
  const index = Math.min(total - 1, Math.floor(offset / count));
  return (
    <View className="flex-1 min-h-0 gap-4">
      <View className="flex-1 min-h-0 gap-3" onLayout={(event) => setHeight(event.nativeEvent.layout.height)}>
        {!entries.length ? <Text className="font-sans text-body text-fg-muted">{empty}</Text> : null}
        {entries.slice(index * count, (index + 1) * count).map((entry, row) => (
          <Pressable key={entry.id} accessibilityRole="button" accessibilityLabel={entry.label} accessibilityHint={entry.meta} accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={() => onSelect(entry.id)} className={`flex-row items-center gap-3 rounded-lg border border-border-default bg-canvas-subtle px-4 ${compact ? 'py-2' : 'py-3'} active:bg-canvas-floating ${disabled ? 'opacity-50' : ''}`} style={{ height: rowHeight }}>
            <Text accessible={false} className="font-mono text-caption text-fg-subtle">{String(index * count + row + 1).padStart(2, '0')}</Text>
            <View className={`flex-1 min-w-0 ${compact ? 'gap-1' : 'gap-2'}`}>
              <Text numberOfLines={2} className={`font-sans-semibold ${compact ? 'text-body' : 'text-title'} ${entry.muted ? 'text-fg-muted' : 'text-fg-default'}`}>{entry.label}</Text>
              {entry.meta ? <Text numberOfLines={compact ? 1 : 2} className={`font-sans text-caption ${entry.muted ? 'text-fg-subtle' : 'text-gold-fg'}`}>{entry.meta}</Text> : null}
            </View>
            <Text accessible={false} className="font-mono text-body text-fg-subtle">›</Text>
          </Pressable>
        ))}
      </View>
      <View className="flex-row items-center gap-3 border-t border-border-default pt-4">
        <Button label={ko.previousPage} disabled={index === 0} onPress={() => setOffset((index - 1) * count)} />
        <Text accessibilityLiveRegion="polite" accessibilityLabel={ko.pageNumber(index + 1, total)} className="flex-1 text-center font-mono text-caption text-fg-subtle">{String(index + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}</Text>
        <Button label={ko.nextPage} disabled={index === total - 1} onPress={() => setOffset((index + 1) * count)} />
      </View>
    </View>
  );
}
