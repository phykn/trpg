import { type RefObject, useState } from 'react';
import { ActivityIndicator, TextInput, View } from 'react-native';

import { IconButton } from '@/components/ui/Button';
import { Notice, Resend } from '@/components/ui/Notice';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';

type Mode = 'open' | 'locked' | 'sending' | 'stuck';

export function CommandBar({ mode, sent, notice, text, onText, onSend, onResend, inputRef }: {
  mode: Mode; sent: string | null; notice: string | null; text: string;
  onText: (t: string) => void; onSend: (text: string) => void; onResend: () => void;
  inputRef?: RefObject<TextInput | null>;
}) {
  const submit = () => {
    const t = text.trim();
    if (!t || mode !== 'open') return;
    onSend(t);
    onText('');
  };
  const ready = mode === 'open' && !!text.trim();
  const [focus, setFocus] = useState(false);
  return (
    <View className="gap-1.5 px-4 pb-3 pt-1.5">
      {notice ? <Notice text={notice} /> : null}
      {mode === 'stuck' ? <Resend onResend={onResend} /> : (
        <View className={`h-11 flex-row items-center rounded-full border bg-canvas-subtle pl-4 pr-1 ${focus ? 'border-gold-fg' : 'border-border-default'} ${mode === 'open' ? '' : 'opacity-60'}`}>
          <TextInput ref={inputRef} value={mode === 'sending' && sent ? sent : text} onChangeText={onText} onSubmitEditing={submit}
            editable={mode === 'open'} onFocus={() => setFocus(true)} onBlur={() => setFocus(false)} maxLength={200}
            accessibilityLabel={ko.command} returnKeyType="send"
            className="h-full min-w-0 flex-1 font-sans text-panel text-fg-default" style={{ outlineStyle: 'none' } as object} />
          {mode === 'sending' ? (
            <View className="h-9 w-9 items-center justify-center"><ActivityIndicator size="small" color={colors.gold.fg} /></View>
          ) : (
            <IconButton icon="send" label={ko.send} tone={ready ? 'gold' : 'plain'} disabled={!ready} onPress={submit} />
          )}
        </View>
      )}
    </View>
  );
}
