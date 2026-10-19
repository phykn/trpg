import { Pressable, Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import { useDialog } from './useDialog';

export function MenuIcon({ open, onPress }: { open: boolean; onPress?: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={ko.menu} accessibilityState={{ disabled: !onPress, expanded: open }}
      disabled={!onPress} onPress={onPress}
      className={`h-[24px] w-[32px] items-center justify-center gap-[3px] rounded-md ${open ? 'bg-accent-muted' : ''} ${onPress ? '' : 'opacity-40'}`}>
      {[0, 1, 2].map((i) => <View key={i} className="h-[2px] w-4 rounded-full bg-fg-muted" />)}
    </Pressable>
  );
}

export function Menu({ onClose, onTitle }: { onClose: () => void; onTitle: () => void }) {
  const ref = useDialog(onClose);
  return (
    <>
      <Pressable accessibilityLabel={ko.closeMenu} className="absolute bottom-0 left-0 right-0 top-0 z-10" onPress={onClose} />
      <View ref={ref} accessibilityRole={'menu' as never}
        className="absolute right-3 top-[34px] z-20 w-[232px] rounded-md border border-border-strong bg-canvas-floating py-1">
        <Pressable accessibilityRole={'menuitem' as never} onPress={onTitle} className="px-3 py-2">
          <Text className="font-sans-semibold text-body text-fg-default">{ko.toTitle}</Text>
          <Text className="font-sans text-chip text-fg-muted">{ko.toTitleSub}</Text>
        </Pressable>
      </View>
    </>
  );
}
