import { Text, View } from 'react-native';

import { IconButton } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Popover } from '@/components/ui/Popover';
import { colors, icon } from '@/design/tokens';
import { text } from '@/design/ui';
import { ko } from '@/locale/ko';
import { findHue } from './speaker';

export type Topic = { name: string; who: string | null };

export function TopicCard({ topic, met, onClose }: { topic: Topic; met: string[]; onClose: () => void }) {
  return (
    <Popover at="bottom-3 left-3 right-3" label={topic.name} onClose={onClose}>
      <View className="flex-row items-center gap-2">
        <Icon name="heard" size={icon.lg} color={colors.topic.fg} width={2} />
        <Text className={text({ kind: 'title' }, 'min-w-0 flex-1 text-topic-fg')}>{topic.name}</Text>
        <IconButton icon="close" label={ko.close} size={32} onPress={onClose} />
      </View>
      <View className="flex-row flex-wrap items-center gap-4">
        {topic.who ? (
          <View className="flex-row items-center gap-1.5">
            <Icon name="person" size={icon.sm} color={findHue(met, topic.who).color} width={2} />
            <Text className={text({ kind: 'panel' })}>{topic.who}</Text>
          </View>
        ) : null}
        <View className="flex-row items-center gap-1.5">
          <Icon name="book" size={icon.sm} color={colors.fg.muted} width={2} />
          <Text className={text({ kind: 'sub' })}>{ko.unheard}</Text>
        </View>
      </View>
    </Popover>
  );
}
