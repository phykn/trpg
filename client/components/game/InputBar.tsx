import { TextInput, View } from 'react-native';

import { IconButton } from '@/components/ui/Button';
import { colors } from '@/design/tokens';
import { control, off, text as type } from '@/design/ui';
import { ko } from '@/locale/ko';

export function InputBar({ partner, locked, text, onText, onSend }: {
  partner: string | null; locked: boolean; text: string; onText: (text: string) => void; onSend: (text: string) => void;
}) {
  const ready = !locked && text.trim().length > 0;
  const send = () => ready && onSend(text.trim());
  const hint = partner ? ko.askTo(partner) : ko.say;
  return (
    <View className="flex-row items-center gap-2 px-3 py-2">
      <TextInput value={text} onChangeText={onText} onSubmitEditing={send} editable={!locked} maxLength={200}
        placeholder={hint} placeholderTextColor={colors.fg.subtle} accessibilityLabel={hint} submitBehavior="submit"
        returnKeyType="send"
        className={`min-w-0 flex-1 ${control.field} ${type.body} ${locked ? off : ''}`} />
      <IconButton icon="send" label={ko.send} tone="gold" size={44} disabled={!ready} onPress={send} />
    </View>
  );
}
