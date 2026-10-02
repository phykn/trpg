import type { ReactNode } from 'react';
import { Modal, Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import { useViewportHeight } from '@/logic/useViewportHeight';
import { Button } from './Button';

export function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const height = useViewportHeight();
  return (
    <Modal transparent animationType="fade" onRequestClose={onClose}>
      <View className="flex-1 items-center bg-overlay">
        <View className="mobile-frame w-full max-w-mobile border-x border-border-default bg-canvas-default" style={{ height }} accessibilityViewIsModal>
          <View className="flex-row items-center justify-between gap-4 border-b border-border-default px-6 py-4">
            <Text accessibilityRole="header" className="flex-1 font-sans-semibold text-title text-fg-default">{title}</Text>
            <Button label={ko.close} onPress={onClose} />
          </View>
          <View className="flex-1 min-h-0 px-6 pb-5 pt-6">{children}</View>
        </View>
      </View>
    </Modal>
  );
}
