import { useState } from 'react';
import { Text, View } from 'react-native';

import { BattleStatus } from '@/components/game/BattleStatus';
import { Notebook } from '@/components/game/Notebook';
import { ActionPreview } from '@/components/ui/ActionPreview';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { MenuGrid } from '@/components/ui/MenuGrid';
import { PagedList } from '@/components/ui/PagedList';
import { Reader } from '@/components/ui/Reader';
import { ko } from '@/locale/ko';
import type { GameAction, GameView } from '@/services/types';

export function Adventure({ view, blocked, onChoose, onNew }: {
  view: GameView;
  blocked: boolean;
  onChoose: (id: string) => Promise<void>;
  onNew: () => void;
}) {
  const [reading, setReading] = useState(true);
  const [group, setGroup] = useState<GameAction['group'] | null>(null);
  const [overlay, setOverlay] = useState<'move' | 'notes' | null>(null);
  const [action, setAction] = useState<GameAction | null>(null);
  const latest = view.journal.filter((entry) => entry.turn === view.revision && entry.kind !== 'action').map((entry) => entry.text);
  const story = latest.length ? latest.join('\n\n') : view.scene.text;
  const text = view.ending ? [story, view.ending.name, view.ending.text, ...view.ending.epilogue].join('\n\n') : story;
  const groups = (['story', 'combat', 'growth', 'item'] as const).filter((key) => view.actions.some((item) => item.group === key));
  const activeGroup = group ?? (groups.length === 1 ? groups[0] : null);
  const actions = view.actions.filter((item) => item.group === activeGroup);
  const entries = (items: GameAction[]) => items.map((item) => ({ id: item.id, label: item.label, meta: [item.enabled ? '' : ko.locked, item.cost].filter(Boolean).join(' · '), muted: !item.enabled }));

  function closeOverlay() {
    if (action) setAction(null);
    else setOverlay(null);
  }

  function selectAction(id: string) {
    const next = view.actions.find((item) => item.id === id);
    if (!next) return;
    if (next.group === 'move' && next.enabled && !next.confirm) {
      setOverlay(null);
      void onChoose(id);
    } else setAction(next);
  }

  return (
    <View className="flex-1 min-h-0">
      <View className="flex-1 min-h-0 gap-5 px-6 pb-5 pt-5">
        {view.combat ? <BattleStatus battle={view.combat} /> : null}
        <View className="flex-1 min-h-0 gap-5" style={{ display: reading ? 'flex' : 'none' }}>
          <Text className="font-sans-semibold text-panel text-gold-fg">{view.ending ? ko.ending : ko.story}</Text>
          <Reader text={text} disabled={blocked} doneLabel={view.ending ? ko.againShort : ko.chooseAction} onDone={view.ending ? onNew : () => setReading(false)} />
        </View>
        {!reading ? (
          <View className="flex-1 min-h-0 gap-4">
            <View className="flex-row items-center gap-3">
              {group && groups.length > 1 ? <Button label={ko.back} onPress={() => setGroup(null)} /> : null}
              <Text accessibilityRole="header" className="flex-1 font-sans-semibold text-title text-fg-default">{activeGroup ? ko.actionGroups[activeGroup] : ko.choose}</Text>
              <Button label={ko.readAgain} onPress={() => setReading(true)} />
            </View>
            {activeGroup ? <PagedList key={activeGroup} disabled={blocked} entries={entries(actions)} onSelect={selectAction} />
              : groups.length ? <MenuGrid disabled={blocked} entries={groups.map((key) => ({ id: key, label: ko.actionGroups[key], meta: ko.actionCount(view.actions.filter((item) => item.group === key).length) }))} onSelect={(id) => setGroup(id as GameAction['group'])} />
                : <Text className="font-sans text-body text-fg-muted">{ko.noActions}</Text>}
          </View>
        ) : null}
      </View>
      <View className="flex-row gap-3 border-t border-border-default px-6 py-3">
        <View className="flex-1"><Button label={ko.story} selected={reading} onPress={() => setReading(true)} /></View>
        <View className="flex-1"><Button label={ko.actionGroups.move} disabled={blocked || !!view.ending} onPress={() => setOverlay('move')} /></View>
        <View className="flex-1"><Button label={ko.notebook} onPress={() => setOverlay('notes')} /></View>
      </View>
      {overlay || action ? (
        <Dialog title={action?.label ?? (overlay === 'move' ? ko.move : ko.notebook)} onClose={closeOverlay}>
          {action ? <ActionPreview action={action} disabled={blocked} onCancel={() => setAction(null)} onConfirm={() => {
            const id = action.id;
            setAction(null);
            setOverlay(null);
            void onChoose(id);
          }} /> : overlay === 'notes' ? <Notebook view={view} /> : <PagedList entries={entries(view.actions.filter((item) => item.group === 'move'))} empty={ko.noMoves} disabled={blocked} onSelect={selectAction} />}
        </Dialog>
      ) : null}
    </View>
  );
}
