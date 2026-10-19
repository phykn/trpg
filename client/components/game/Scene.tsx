import { View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';
import { Item, Pill, Row } from './Row';

// Where the player is and what is here; every name starts a sentence when tapped.
export function Scene({ scene, onDraft }: { scene: GameView['scene']; onDraft?: (text: string) => void }) {
  const draft = (text: string) => (onDraft ? () => onDraft(text) : undefined);
  const around = scene.people.length + scene.things.length + scene.obstacles.length + scene.tags.length;
  return (
    <>
      <Row icon="pin" label={ko.row.here}>
        <Item strong>{scene.place.name}</Item>
        {scene.exits.map((e) => {
          // A locked way points at what locks it: the tap starts a sentence about that obstacle instead.
          const lock = e.blocked ? scene.obstacles.find((o) => o.fill < o.boxes && o.blocks.includes(e.name)) : undefined;
          return (
            <Pill key={e.id} label={e.name} icon={e.blocked ? 'lock' : 'arrow'} color={colors.fg.muted} dim={e.blocked}
              onPress={!e.blocked ? draft(ko.draft.go(e.name)) : lock ? draft(ko.draft.thing(lock.name)) : undefined} />
          );
        })}
      </Row>
      {around ? (
        <Row icon="eye" label={ko.row.around}>
          {scene.people.map((p) => <Pill key={p.id} label={p.name} color={colors.kind.person} onPress={draft(ko.draft.person(p.name))} />)}
          {scene.things.map((x) => <Pill key={x.id} label={x.name} color={colors.kind.thing} onPress={draft(ko.draft.thing(x.name))} />)}
          {scene.obstacles.map((o) => {
            // An overcome obstacle stays in the scene but reads as done, since a single box is never drawn.
            const done = o.fill >= o.boxes;
            return (
              <View key={o.id} className="flex-row items-center gap-1">
                <Pill label={o.name} color={colors.kind.obstacle} icon={done ? 'check' : undefined} dim={done}
                  onPress={done ? undefined : draft(ko.draft.thing(o.name))} />
                {o.boxes > 1 && !done ? <Boxes fill={o.fill} boxes={o.boxes} /> : null}
              </View>
            );
          })}
          {scene.tags.map((t) => (
            <Item key={`${t.owner}${t.slot}`} color={t.kind === 'edge' ? colors.gold.fg : colors.danger.fg}>{t.name}</Item>
          ))}
        </Row>
      ) : null}
    </>
  );
}
