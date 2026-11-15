import type { ReactNode } from 'react';
import { Pressable, View } from 'react-native';

import { ko } from '@/locale/ko';

// Covers the play screen; a tap outside the card closes it.
export function Overlay({ full, onClose, children }: { full?: boolean; onClose: () => void; children: ReactNode }) {
  return (
    <View className="absolute inset-0 justify-end">
      <Pressable accessibilityLabel={ko.close} onPress={onClose} className="absolute inset-0 bg-overlay" />
      <View className={full ? 'min-h-0 flex-1 pt-6' : 'max-h-[85%]'}>{children}</View>
    </View>
  );
}
