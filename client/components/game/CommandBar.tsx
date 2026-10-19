import { useState } from 'react';
import { TextInput, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { useViewportHeight } from '@/logic/useViewportHeight';
import type { Button as Choice, Command } from '@/services/types';

// Below this height three suggestion buttons left the scene two lines per page; they fold behind a toggle.
const SHORT_SCREEN = 700;

export function CommandBar({ buttons, disabled, onSend }: { buttons: Choice[]; disabled: boolean; onSend: (command: Command) => void }) {
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const compact = useViewportHeight() < SHORT_SCREEN;
  const submit = () => {
    const said = text.trim();
    if (!said || disabled) return;
    setText('');
    onSend({ text: said });
  };
  const shown = !compact || open;
  return (
    <View className="gap-2 border-t border-border-default px-6 py-3">
      {shown ? buttons.map((b) => (
        <Button key={b.id} label={b.label} disabled={disabled || !b.enabled} onPress={() => { setOpen(false); onSend({ action_id: b.id }); }} />
      )) : null}
      <View className="flex-row items-center gap-2">
        <TextInput accessibilityLabel={ko.inputLabel} value={text} onChangeText={setText} maxLength={200} editable={!disabled}
          placeholder={ko.inputPlaceholder} placeholderTextColor={colors.fg.subtle} returnKeyType="send" onSubmitEditing={submit}
          className="min-h-11 min-w-0 flex-1 rounded-md border border-border-strong bg-canvas-subtle px-3 py-2 font-sans text-body text-fg-default" />
        {compact && buttons.length ? <Button label={open ? ko.hideSuggestions : ko.suggestions} selected={open} onPress={() => setOpen(!open)} /> : null}
        <Button label={ko.submit} primary disabled={disabled || !text.trim()} onPress={submit} />
      </View>
    </View>
  );
}
