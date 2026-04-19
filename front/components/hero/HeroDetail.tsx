import { View, Text } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';
import { LabeledRow, InlineNodes } from '@/components/atoms';
import type { Hero } from '@/types/game';

export function HeroDetail({ hero }: { hero: Hero }) {
  const equipped = (hero.inventory || []).filter(it => it.eq);
  const carried  = (hero.inventory || []).filter(it => !it.eq);
  const expPct = Math.min(100, (hero.exp / hero.expMax) * 100);
  return (
    <View style={{
      marginTop: Theme.space.sm,
      paddingVertical: Theme.space.md, paddingHorizontal: Theme.space.md + 2,
      backgroundColor: Theme.bgCard, borderWidth: 1, borderColor: Theme.border,
      borderRadius: Theme.radius.md, minHeight: 148,
      gap: Theme.space.sm + 2,
    }}>
      <LabeledRow label="경험" align="center">
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: Theme.space.md }}>
          <View style={{
            flex: 1, height: 6, borderRadius: 3,
            backgroundColor: `${Theme.exp}1A`, overflow: 'hidden',
          }}>
            <View style={{
              position: 'absolute', top: 0, bottom: 0, left: 0,
              width: `${expPct}%`,
              backgroundColor: Theme.exp, borderRadius: 3,
            }} />
          </View>
          <Text style={{
            ...typeStyle('caption'),
            color: Theme.text, fontFamily: Theme.fonts.monoRegular,
            fontVariant: ['tabular-nums'],
          }}>
            {hero.exp}<Text style={{ color: Theme.textFaint }}>/{hero.expMax}</Text>
          </Text>
        </View>
      </LabeledRow>

      <LabeledRow label="능력" mono>
        <InlineNodes entries={Object.entries(hero.stats) as [string, number][]} />
      </LabeledRow>

      {hero.skills?.length > 0 && <LabeledRow label="기술">{hero.skills.join(' · ')}</LabeledRow>}
      {equipped.length > 0 && <LabeledRow label="장비">{equipped.map(it => it.n).join(' · ')}</LabeledRow>}
      {carried.length > 0 && (
        <LabeledRow label="소지">
          {carried.map(it => it.q > 1 ? `${it.n} ×${it.q}` : it.n).join(' · ')}
        </LabeledRow>
      )}
      {hero.companions?.length > 0 && <LabeledRow label="동료">{hero.companions.join(' · ')}</LabeledRow>}
    </View>
  );
}
