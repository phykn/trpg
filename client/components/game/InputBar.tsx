import { useState } from 'react';
import { TextInput, View } from 'react-native';

import { IconButton } from '@/components/ui/Button';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';

export function InputBar({ partner, locked, onSend }: { partner: string | null; locked: boolean; onSend: (text: string) => void }) {
  const [text, setText] = useState('');
  const ready = !locked && text.trim().length > 0;
  const send = () => {
    if (!ready) return;
    onSend(text.trim());
    setText('');
  };
  return (
    <View className="flex-row items-center gap-2 px-3 py-2">
      <TextInput value={text} onChangeText={setText} onSubmitEditing={send} editable={!locked} maxLength={200}
        placeholder={partner ? ko.askTo(partner) : ko.say} placeholderTextColor={colors.fg.subtle}
        accessibilityLabel={partner ? ko.askTo(partner) : ko.say} submitBehavior="submit" returnKeyType="send"
        className={`h-11 min-w-0 flex-1 rounded-full border border-border-strong bg-canvas-floating px-4 font-sans text-body text-fg-default ${locked ? 'opacity-60' : ''}`} />
      <IconButton icon="send" label={ko.send} tone="gold" size={44} disabled={!ready} onPress={send} />
    </View>
  );
}
