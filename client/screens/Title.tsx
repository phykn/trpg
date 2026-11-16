import { ScrollView, Text, View } from 'react-native';

import { Choice } from '@/components/ui/Sheet';
import { text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { Story } from '@/services/types';

export function Title({ stories, saved, onStart, onResume }: {
  stories: Story[]; saved: string | null; onStart: (story: string) => void; onResume: () => void;
}) {
  return (
    <View className="min-h-0 flex-1 px-4 py-8">
      <Text accessibilityRole="header" className={`py-12 text-center ${text.display}`}>
        {ko.brand}
      </Text>
      <ScrollView contentContainerClassName="gap-3">
        {saved ? <Choice primary label={ko.resume} onPress={onResume} /> : null}
        {stories.map((s) => <Choice key={s.story} label={s.title} onPress={() => onStart(s.story)} />)}
      </ScrollView>
    </View>
  );
}
