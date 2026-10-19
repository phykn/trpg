import { useState } from 'react';
import { ActivityIndicator, Pressable, Text, TextInput, View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';

type Mode = 'open' | 'locked' | 'sending' | 'stuck' | 'blocked';

export function CommandBar({ mode, sent, notice, placeholder, onSend, onResend, onNew }: {
  mode: Mode; sent: string | null; notice: string | null; placeholder: string;
  onSend: (text: string) => void; onResend: () => void; onNew: () => void;
}) {
  const [text, setText] = useState('');
  const submit = () => {
    const t = text.trim();
    if (!t || mode !== 'open') return;
    onSend(t);
    setText('');
  };
  return (
    <View className="gap-1 border-t border-border-default px-4 pb-2 pt-1">
      {notice ? <Text accessibilityRole="alert" className="font-sans text-chip text-danger-fg">{notice}</Text> : null}
      {mode === 'stuck' ? (
        <View className="flex-row items-center gap-2">
          <Text className="flex-1 font-sans text-chip text-fg-muted">{ko.stuck}</Text>
          <Pressable accessibilityRole="button" onPress={onResend} className="rounded-md bg-gold-fg px-3 py-2">
            <Text className="font-sans-semibold text-panel text-fg-on-emphasis">{ko.resend}</Text>
          </Pressable>
        </View>
      ) : mode === 'blocked' ? (
        <View className="flex-row items-center gap-2">
          <Text className="flex-1 font-sans text-chip text-danger-fg">{ko.blocked}</Text>
          <Pressable accessibilityRole="button" onPress={onNew} className="rounded-md border border-border-default px-3 py-2">
            <Text className="font-sans text-panel text-fg-default">{ko.toTitle}</Text>
          </Pressable>
        </View>
      ) : (
        <View className="flex-row items-center gap-2">
          <TextInput value={mode === 'sending' && sent ? sent : text} onChangeText={setText} onSubmitEditing={submit}
            editable={mode === 'open'} placeholder={placeholder} placeholderTextColor={colors.fg.subtle} maxLength={200}
            accessibilityLabel={placeholder} returnKeyType="send"
            className="h-10 flex-1 rounded-md border border-border-default px-3 font-sans text-body text-fg-default" />
          {mode === 'sending' ? <ActivityIndicator color={colors.gold.fg} /> : (
            <Pressable accessibilityRole="button" accessibilityState={{ disabled: mode !== 'open' }} disabled={mode !== 'open'}
              onPress={submit} className={`h-10 justify-center rounded-md bg-gold-fg px-3 ${mode !== 'open' ? 'opacity-50' : ''}`}>
              <Text className="font-sans-semibold text-panel text-fg-on-emphasis">{ko.send}</Text>
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
}
