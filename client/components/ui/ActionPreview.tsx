import { View, Text } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameAction } from '@/services/types';
import { Reader } from './Reader';

export function ActionPreview({ action, disabled, onCancel, onConfirm }: {
  action: GameAction;
  disabled: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const text = [
    action.description,
    action.enabled ? '' : action.blocked,
    action.confirm ? ko.importantChoice : '',
    action.enabled ? ko.confirmHelp : '',
  ].filter(Boolean).join('\n\n');
  return (
    <View className="flex-1 min-h-0 gap-5">
      <Text className="font-sans text-body text-gold-fg">{action.cost}</Text>
      <Reader key={action.id} text={text} disabled={disabled} doneLabel={action.enabled ? ko.confirm : ko.back} onDone={action.enabled ? onConfirm : onCancel} />
    </View>
  );
}
