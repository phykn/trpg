import { useState } from 'react';
import { Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { MenuGrid } from '@/components/ui/MenuGrid';
import { PagedList } from '@/components/ui/PagedList';
import { Reader } from '@/components/ui/Reader';
import { ko } from '@/locale/ko';
import type { GameView, NamedText } from '@/services/types';

type Section = 'objective' | 'clues' | 'people' | 'bag' | 'history' | 'status';
const sections: Section[] = ['objective', 'clues', 'people', 'bag', 'history', 'status'];

export function Notebook({ view }: { view: GameView }) {
  const [section, setSection] = useState<Section | null>(null);
  const [entry, setEntry] = useState<NamedText | null>(null);
  const records: Record<Section, NamedText[]> = {
    objective: [{ id: 'objective', name: ko.objective, text: view.objective }, { ...view.scene, name: ko.currentPlace }],
    clues: view.knowledge,
    people: view.characters,
    bag: [...view.inventory, ...view.skills],
    history: [...view.journal].reverse().map((line, i) => ({ id: String(i), name: ko.recordTurn(line.turn), text: line.text })),
    status: [{ id: 'status', name: view.player_name, text: [view.role, view.alert, ko.saveHelp].join('\n\n') }],
  };
  const titles: Record<Section, string> = { objective: ko.objective, clues: ko.clues, people: ko.people, bag: ko.bag, history: ko.history, status: ko.status };
  return (
    <View className="flex-1 min-h-0 gap-5">
      {section ? (
        <View className="flex-row items-center gap-3">
          <Button label={ko.back} onPress={() => entry ? setEntry(null) : setSection(null)} />
          <Text accessibilityRole="header" className="flex-1 font-sans-semibold text-title text-gold-fg">{entry?.name ?? titles[section]}</Text>
        </View>
      ) : <Text className="font-sans text-panel text-fg-muted">{ko.notebookHelp}</Text>}
      <View className="flex-1 min-h-0" style={{ display: entry ? 'none' : 'flex' }}>
        {section ? <PagedList key={section} entries={records[section].map((item) => ({ id: item.id, label: section === 'history' ? item.text : item.name, meta: section === 'history' ? item.name : item.text }))}
          onSelect={(id) => setEntry(records[section].find((item) => item.id === id) ?? null)}
          empty={section === 'clues' ? ko.noClues : section === 'bag' ? ko.emptyBag : ko.noEntries} />
          : <MenuGrid entries={sections.map((key) => ({ id: key, label: titles[key], meta: ko.entryCount(records[key].length) }))} onSelect={(id) => setSection(id as Section)} />}
      </View>
      {entry ? <Reader key={entry.id} text={entry.text} onDone={() => setEntry(null)} doneLabel={ko.back} /> : null}
    </View>
  );
}
