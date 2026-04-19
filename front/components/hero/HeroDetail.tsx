import { View } from 'react-native';
import { LabeledRow, InlineNodes, ExpandGroup } from '@/components/ui';
import type { Hero, EquipItem } from '@/types/domain';

const PLACEHOLDER = '—';
const joinOrDash = (arr: string[]) => (arr.length > 0 ? arr.join(' · ') : PLACEHOLDER);

export function HeroDetail({ hero }: { hero: Hero }) {
  const equipped = Object.values(hero.equipment)
    .filter((it): it is EquipItem => it !== null);
  const carried = hero.inventory;

  return (
    <View className="mt-2 px-3.5 py-3 bg-canvas-subtle border border-border-default rounded-md gap-2.5">
      <ExpandGroup>
        <LabeledRow label="능력" mono>
          <InlineNodes entries={Object.entries(hero.stats) as [string, number][]} />
        </LabeledRow>

        <LabeledRow label="특징">{`${hero.race} ${hero.class}`}</LabeledRow>
        <LabeledRow label="기술">{joinOrDash(hero.skills ?? [])}</LabeledRow>
        <LabeledRow label="장비">{joinOrDash(equipped.map((it) => it.name))}</LabeledRow>
        <LabeledRow label="소지">
          {joinOrDash(carried.map((it) => (it.qty > 1 ? `${it.name} ×${it.qty}` : it.name)))}
        </LabeledRow>
        <LabeledRow label="상태">{joinOrDash(hero.status ?? [])}</LabeledRow>
        <LabeledRow label="동료">{joinOrDash(hero.companions ?? [])}</LabeledRow>
      </ExpandGroup>
    </View>
  );
}
