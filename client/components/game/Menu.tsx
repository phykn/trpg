import { Pressable, Text, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { useEnter } from '@/components/ui/motion';
import { useDialog } from '@/components/ui/useDialog';
import { ko } from '@/locale/ko';

export function Menu({ onClose, onTitle }: { onClose: () => void; onTitle: () => void }) {
  const ref = useDialog(onClose);
  const enter = useEnter(-6);
  return (
    <>
      <Pressable accessibilityLabel={ko.closeMenu} className="absolute bottom-0 left-0 right-0 top-0 z-10" onPress={onClose} />
      {/* Animated views take no className, so the dropdown is placed by style. */}
      <Animated.View style={[{ position: 'absolute', right: 12, top: 42, zIndex: 20 }, enter]}>
        <View ref={ref} accessibilityRole={'menu' as never}
          className="w-[168px] rounded-2xl border border-border-strong bg-canvas-floating p-1">
          <Pressable accessibilityRole={'menuitem' as never} onPress={onTitle}
            style={pressed} className="h-10 flex-row items-center gap-2.5 rounded-xl px-3">
            <Icon name="home" size={16} />
            <Text className="font-sans-semibold text-panel text-fg-default">{ko.toTitle}</Text>
          </Pressable>
        </View>
      </Animated.View>
    </>
  );
}
