import type { ReactNode } from 'react';
import { Pressable, View } from 'react-native';

import { ko } from '@/locale/ko';
import { cn, surface } from '@/design/ui';
import { useDialog } from './useDialog';

export function Popover({ at, label, onClose, children }: { at: string; label: string; onClose: () => void; children: ReactNode }) {
  const dialog = useDialog(onClose);
  return (
    <View className="absolute inset-0 z-10">
      <Pressable accessibilityLabel={ko.close} onPress={onClose} className="absolute inset-0" />
      <View ref={dialog} accessibilityRole={'dialog' as never} accessibilityLabel={label} aria-modal
        className={cn(surface({ kind: 'float' }), 'absolute', at)}>
        {children}
      </View>
    </View>
  );
}
