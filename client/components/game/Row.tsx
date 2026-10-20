import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Icon, type IconName } from '@/components/ui/Icon';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Tag } from '@/services/types';

// Every row starts with its icon in one fixed column, so the content of all rows shares one left edge.
// A row wraps instead of truncating, so names in it are never shortened.
export function Row({ icon, tone, label, children, inset }: {
  icon: IconName; tone?: string; label: string; children: ReactNode; inset?: boolean;
}) {
  return (
    <View accessibilityLabel={label} className={`flex-row items-start py-[3px] ${inset ? 'px-3' : 'px-4'}`}>
      <View className="h-[22px] w-5 justify-center">
        <Icon name={icon} size={14} color={tone ?? colors.fg.subtle} />
      </View>
      <View className="ml-2 min-w-0 flex-1 flex-row flex-wrap items-center" style={{ columnGap: 6, rowGap: 4 }}>
        {children}
      </View>
    </View>
  );
}

export function Item({ children, dim, color = colors.fg.default, strong }: {
  children: ReactNode; dim?: boolean; color?: string; strong?: boolean;
}) {
  return (
    <Text className={`${strong ? 'font-sans-semibold' : 'font-sans'} text-chip`}
      style={{ color, opacity: dim ? 0.45 : 1, lineHeight: 22 }}>
      {children}
    </Text>
  );
}

// Tags of one name, kind and life count once in a roll, so they show once; the life says when each goes
// ("불리함, 불리함" with no end in sight, qa_test/runs/play-3-bold 17, play-3-talker 46, play-4-odd 15).
export function TagItems({ tags }: { tags: Tag[] }) {
  const seen = new Set<string>();
  return (
    <>
      {tags.filter((t) => {
        const k = `${t.kind}|${t.life}|${t.name}`;
        return !seen.has(k) && !!seen.add(k);
      }).map((t) => (
        <Item key={`${t.owner ?? ''}${t.slot}`} color={t.kind === 'edge' ? colors.gold.fg : colors.danger.fg}>
          {t.name}
          {ko.tagLife[t.life] ? <Text style={{ color: colors.fg.muted }}>{` · ${ko.tagLife[t.life]}`}</Text> : null}
        </Item>
      ))}
    </>
  );
}

// A name the player can tap to start a sentence about it.
export function Pill({ label, color = colors.fg.default, icon, onPress, dim }: {
  label: string; color?: string; icon?: IconName; onPress?: () => void; dim?: boolean;
}) {
  return (
    <Pressable accessibilityRole={onPress ? 'button' : undefined} accessibilityLabel={label} disabled={!onPress} onPress={onPress}
      style={({ pressed: p }) => ({ opacity: dim ? 0.45 : p ? 0.7 : 1 })}
      className="h-[22px] flex-row items-center gap-1 rounded-full border border-border-default px-2">
      {icon ? <Icon name={icon} size={11} color={color} width={2.2} /> : null}
      <Text className="font-sans text-chip" style={{ color, lineHeight: 16 }}>{label}</Text>
    </Pressable>
  );
}
