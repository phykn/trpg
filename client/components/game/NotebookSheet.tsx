import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { Button, pressed } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { control, surface, text, tone } from '@/design/ui';
import { ko } from '@/locale/ko';
import { findLine, GROUPS } from '@/logic/notebook';
import type { GameView, Group, Line } from '@/services/types';
import { Marks } from './Marks';

const Unread = () => <View className="h-1.5 w-1.5 rounded-full bg-gold-fg" />;
const struck = (line: Line) => (line.struck ? 'line-through opacity-60' : '');

// A folded card shows two lines of the intro; the hidden copy measures whether the rest is cut.
function Intro({ words, open, onCut }: { words: string; open: boolean; onCut: (cut: boolean) => void }) {
  const [shown, setShown] = useState(0);
  const [full, setFull] = useState(0);
  useEffect(() => { if (shown && full) onCut(full > shown + 1); }, [shown, full]);   // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <View>
      <Text numberOfLines={open ? undefined : 2} onLayout={(e) => setShown(e.nativeEvent.layout.height)} className={text.note}>
        {words}
      </Text>
      {open ? null : (
        <Text aria-hidden onLayout={(e) => setFull(e.nativeEvent.layout.height)} pointerEvents="none"
          className={`absolute left-0 right-0 top-0 opacity-0 ${text.note}`}>{words}</Text>
      )}
    </View>
  );
}

// One card. It opens in place when it holds more than it shows: the rest of the intro, gathered lines, acts.
function NotebookLine({ line, view, open, locked, onToggle, onLine, onAct, onLayout }: {
  line: Line; view: GameView; open: boolean; locked: boolean; onToggle: () => void; onLine: (id: number) => void;
  onAct: (act: string) => void; onLayout: (y: number) => void;
}) {
  const [cut, setCut] = useState(false);
  const about = line.about.flatMap((id) => findLine(view, id)?.line ?? []);
  const opens = cut || about.length > 0 || line.acts.length > 0;
  return (
    <View onLayout={(e) => onLayout(e.nativeEvent.layout.y)}
      className={`gap-2 ${surface.card}`}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} disabled={!opens} onPress={onToggle}
        style={pressed} className="gap-1.5">
        <View className="flex-row items-center gap-2">
          <Text className={`min-w-0 flex-1 ${text.body} ${struck(line)}`}>{line.text}</Text>
          {line.new ? <Unread /> : null}
        </View>
        {line.intro ? <Intro words={line.intro} open={open} onCut={setCut} /> : null}
        <Marks marks={line.marks} />
      </Pressable>
      {open && about.length ? (
        <View className="gap-1.5">
          {about.map((l) => (
            <Pressable key={l.id} accessibilityRole="button" onPress={() => onLine(l.id)} style={pressed}
              className={`gap-1 ${surface.well}`}>
              <Text className={`${text.small} ${struck(l)}`}>{l.text}</Text>
              <Marks marks={l.marks} />
            </Pressable>
          ))}
        </View>
      ) : null}
      {open && line.acts.length ? (
        <View className="gap-2">
          {line.acts.map((a) => <Button key={a.id} tone="secondary" label={a.label} disabled={locked} onPress={() => onAct(a.id)} />)}
        </View>
      ) : null}
    </View>
  );
}

export function NotebookSheet({ view, group, line, locked, onGroup, onLine, onAct, onConclude, onClose }: {
  view: GameView; group: Group; line?: number; locked: boolean; onGroup: (group: Group) => void;
  onLine: (id: number | undefined) => void; onAct: (act: string) => void; onConclude?: () => void; onClose: () => void;
}) {
  const scroll = useRef<ScrollView>(null);
  const tops = useRef<Record<number, number>>({});
  // A line opened from elsewhere (the chat, another line) scrolls into view; one unfolded in place stays put.
  const aim = useRef<number | undefined>(undefined);
  const toggled = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (line !== undefined && line !== toggled.current) {
      aim.current = line;
      if (tops.current[line] !== undefined) scroll.current?.scrollTo({ y: tops.current[line], animated: false });
    }
    toggled.current = undefined;
  }, [line, group]);
  function place(id: number, y: number) {
    tops.current[id] = y;
    if (id === aim.current) {
      scroll.current?.scrollTo({ y, animated: false });
      aim.current = undefined;
    }
  }
  function toggle(id: number) {
    toggled.current = id;
    onLine(id === line ? undefined : id);
  }
  return (
    <Sheet full title={ko.notebook} icon="book" onClose={onClose}>
      <View accessibilityRole="tablist" className="flex-row gap-1">
        {GROUPS.map((g) => (
          <Pressable key={g} accessibilityRole="tab" accessibilityState={{ selected: g === group }} onPress={() => onGroup(g)}
            style={pressed}
            className={`${control.tab} ${g === group ? tone.active : tone.quiet}`}>
            <Text numberOfLines={1} className={g === group ? text.tabOn : text.tab}>
              {ko.groups[g]}
            </Text>
            {view.notebook[g].some((l) => l.new) ? <Unread /> : null}
          </Pressable>
        ))}
      </View>
      <ScrollView key={group} ref={scroll} className="min-h-0 flex-1" contentContainerClassName="gap-2">
        {view.notebook[group].map((l) => (
          <NotebookLine key={l.id} line={l} view={view} open={l.id === line} locked={locked}
            onToggle={() => toggle(l.id)} onLine={onLine} onAct={onAct}
            onLayout={(y) => place(l.id, y)} />
        ))}
      </ScrollView>
      {onConclude ? <Button tone="secondary" icon="flag" label={ko.conclude} onPress={onConclude} /> : null}
    </Sheet>
  );
}
