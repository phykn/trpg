import { Modal, Pressable, Text, View } from 'react-native';

import { shadow, toneColor } from '@/design/tokens';
import { compose, ko } from '@/locale/ko';
import type { ConfirmInfo } from './types';

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
          text: compose.affinity(info.trust),
        };

  return (
    <Modal transparent visible animationType="fade" onRequestClose={onCancel}>
      <Pressable
        onPress={onCancel}
        className="flex-1 items-center justify-center px-6"
        style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}
      >
        <Pressable
          onPress={(e) => e.stopPropagation()}
          className="bg-[#262931] border border-[rgba(255,255,255,0.18)] rounded-md p-4 gap-3 w-full"
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
              accessibilityLabel={ko.level.cancel}
              className="px-3 py-2 rounded-sm border border-border-default active:bg-canvas-inset"
            >
              <Text className="font-sans text-body text-fg-default">{ko.level.cancel}</Text>
            </Pressable>
            <Pressable
              onPress={onConfirm}
              accessibilityRole="button"
              accessibilityLabel={info.confirmLabel ?? ko.confirm.ok}
              className="px-3 py-2 rounded-sm bg-accent-muted active:opacity-80"
            >
              <Text className="font-sans-semibold text-body text-accent-fg">
                {info.confirmLabel ?? ko.confirm.ok}
              </Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
