import { Modal, Pressable, Text, View } from 'react-native';

import { shadow, toneColor } from '@/design/tokens';
import type { ConfirmInfo } from '@/types/ui';

export function ConfirmDialog({ info, onConfirm, onCancel }: {
  info: ConfirmInfo;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const trust =
    info.trust === undefined
      ? null
      : {
          cls: info.trust > 0 ? 'text-success-fg' : 'text-danger-fg',
          text: `호감도 ${info.trust > 0 ? '+' : ''}${info.trust}`,
        };

  return (
    <Modal transparent visible animationType="fade" onRequestClose={onCancel}>
      <Pressable
        onPress={onCancel}
        className="flex-1 items-center justify-center px-6"
        style={{ backgroundColor: 'rgba(0,0,0,0.4)' }}
      >
        <Pressable
          onPress={(e) => e.stopPropagation()}
          className="bg-canvas-default border border-border-default rounded-md p-4 gap-3 w-full"
          style={{ maxWidth: 320, ...shadow.floating }}
        >
          <View className="gap-1">
            <View className="flex-row items-baseline gap-2">
              <Text
                numberOfLines={1}
                className="font-serif-medium text-title text-fg-default flex-1"
              >
                {info.title}
              </Text>
              {trust ? (
                <Text className={`font-mono text-caption ${trust.cls}`}>
                  {trust.text}
                </Text>
              ) : info.risk ? (
                <Text
                  className="font-sans-semibold text-caption"
                  style={{ color: toneColor[info.risk.tone] }}
                >
                  {info.risk.label}
                </Text>
              ) : null}
            </View>
            {info.subtitle && (
              <Text className="font-sans italic text-caption text-fg-muted">
                {info.subtitle}
              </Text>
            )}
          </View>
          {info.blurb && (
            <Text className="font-sans text-body text-fg-default">
              {info.blurb}
            </Text>
          )}
          <View className="flex-row gap-2 justify-end">
            <Pressable
              onPress={onCancel}
              accessibilityRole="button"
              accessibilityLabel="취소"
              className="px-3 py-2 rounded-sm border border-border-default active:bg-canvas-inset"
            >
              <Text className="font-sans text-body text-fg-default">취소</Text>
            </Pressable>
            <Pressable
              onPress={onConfirm}
              accessibilityRole="button"
              accessibilityLabel={info.confirmLabel ?? '확인'}
              className="px-3 py-2 rounded-sm bg-accent-muted active:opacity-80"
            >
              <Text className="font-sans-semibold text-body text-accent-fg">
                {info.confirmLabel ?? '확인'}
              </Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
