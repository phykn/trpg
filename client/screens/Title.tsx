import { Pressable, ScrollView, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { Story } from '@/services/types';

// "프롤로그: 사라진 벨트" reads as a small part label over the story's name.
function splitTitle(title: string) {
  const at = title.indexOf(': ');
  return at < 0 ? { part: null, name: title } : { part: title.slice(0, at), name: title.slice(at + 2) };
}

function StoryCard({ title, onPress }: { title: string; onPress: () => void }) {
  const { part, name } = splitTitle(title);
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={title} onPress={onPress} style={pressed}
      className={control({ kind: 'row', tone: 'quiet' }, 'py-3 bg-canvas-floating')}>
      <View className="min-w-0 flex-1 gap-0.5">
        {part ? <Text className={text({ kind: 'head' }, 'text-gold-fg')}>{part}</Text> : null}
        <Text numberOfLines={1} className={text({ kind: 'title' }, 'font-serif')}>{name}</Text>
      </View>
      <Icon name="next" size={icon.md} color={colors.fg.subtle} width={2} />
    </Pressable>
  );
}

export function Title({ stories, saved, onStart, onResume }: {
  stories: Story[]; saved: string | null; onStart: (story: string) => void; onResume: () => void;
}) {
  return (
    <View className="min-h-0 flex-1 px-5 pb-6 pt-20">
      <View className="gap-3">
        <Icon name="dice" size={28} color={colors.gold.fg} width={1.6} />
        <Text accessibilityRole="header" className={text({ kind: 'display' })}>{ko.brand}</Text>
        <View className="h-0.5 w-8 bg-gold-fg" />
      </View>
      <View className="min-h-0 flex-1" />
      <ScrollView className="max-h-full grow-0" contentContainerClassName="gap-2.5">
        {saved ? (
          <Pressable accessibilityRole="button" accessibilityLabel={ko.resume} onPress={onResume} style={pressed}
            className={control({ kind: 'button', tone: 'active' }, 'mb-2')}>
            <Icon name="step" size={icon.sm} color={colors.fg['on-emphasis']} fill />
            <Text className={text({ kind: 'strong', on: true })}>{ko.resume}</Text>
          </Pressable>
        ) : null}
        {stories.map((s) => <StoryCard key={s.story} title={s.title} onPress={() => onStart(s.story)} />)}
      </ScrollView>
    </View>
  );
}
