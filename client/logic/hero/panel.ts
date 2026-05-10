import { characterMeta, formatInventoryItem, joinOrDash, withDeath } from '@/components/ui';
import { compose, ko } from '@/locale/ko';
import type { PanelAction, PanelActions, PanelSlot } from '@/logic/info-panel';

import type { Equipment, EquipItem, EquipSlot, Hero, InventoryItem } from './types';

export type BuildHeroSlotOpts = {
  onLevelUpOpen?: () => void;
};

export function buildHeroSlot(hero: Hero, opts?: BuildHeroSlotOpts): PanelSlot {
  const equipped = Object.values(hero.equipment).filter((it): it is EquipItem => it != null);
  const actionGroups = heroActionGroups(hero);
  const titleAction = hero.canLevelUp && opts?.onLevelUpOpen
    ? { label: ko.level.title, onPress: opts.onLevelUpOpen }
    : undefined;
  return {
    id: 'hero',
    chip: { short: hero.name, dot: hero.canLevelUp },
    panel: {
      title: withDeath(hero.name, hero.alive),
      meta: [{ text: characterMeta(hero.level, hero.raceJob, hero.gender) }],
      titleAction,
      barSplit: [
        { label: 'HP', value: hero.hp, max: hero.hpMax, tone: 'hp', display: `${hero.hp}/${hero.hpMax}` },
        { label: 'MP', value: hero.mp, max: hero.mpMax, tone: 'mp', display: `${hero.mp}/${hero.mpMax}` },
      ],
      sections: [
        { label: ko.hero.ability, nodes: hero.stats.map((s): [string, number] => [s.label, s.value]) },
        { label: ko.hero.equip, text: joinOrDash(equipped.map((it) => it.name)) },
        { label: ko.hero.inventory, text: joinOrDash(hero.inventory.map(formatInventoryItem)) },
        { label: ko.hero.skill, text: joinOrDash(hero.skills) },
        { label: ko.hero.companion, text: joinOrDash(hero.companions) },
        { label: ko.panel.traits, text: joinOrDash(hero.status) },
      ],
      actions: actionGroups.length > 0 ? actionGroups : undefined,
    },
  };
}

function heroActionGroups(hero: Hero): PanelActions[] {
  const inventoryActions = hero.inventory.flatMap((item) => itemActions(item, hero.equipment));
  const equipmentActions = (Object.entries(hero.equipment) as [EquipSlot, EquipItem | null | undefined][])
    .flatMap(([, item]) => unequipAction(item));
  return [
    ...(inventoryActions.length > 0 ? [{ label: ko.hero.inventory, items: inventoryActions }] : []),
    ...(equipmentActions.length > 0 ? [{ label: ko.hero.equip, items: equipmentActions }] : []),
  ];
}

function itemActions(item: InventoryItem, equipment: Equipment): PanelAction[] {
  if (!item.id) return [];
  const actions: PanelAction[] = [];
  if (item.canUse) {
    actions.push({
      kind: 'graph_action',
      label: compose.useItem(item.name),
      graphAction: { verb: 'use', what: item.id },
    });
  }

  const equipSlot = preferredEquipSlot(item, equipment);
  if (equipSlot) {
    actions.push({
      kind: 'graph_action',
      label: compose.equipItem(item.name),
      graphAction: { verb: 'transfer', what: item.id, how: 'equip', to: equipSlot },
    });
  }
  return actions;
}

function unequipAction(item: EquipItem | null | undefined): PanelAction[] {
  if (!item?.id) return [];
  return [{
    kind: 'graph_action',
    label: compose.unequipItem(item.name),
    graphAction: { verb: 'transfer', what: item.id, how: 'unequip' },
  }];
}

function preferredEquipSlot(item: InventoryItem, equipment: Equipment): EquipSlot | null {
  const slots = item.equipSlots ?? [];
  if (slots.length === 0) return null;
  return slots.find((slot) => !equipment[slot]) ?? slots[0] ?? null;
}
