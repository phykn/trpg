import { useLayoutEffect, useRef, useState } from 'react';
import { type NativeSyntheticEvent, Pressable, TextInput, type TextInputKeyPressEventData, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, text as type } from '@/design/ui';
import { ko } from '@/locale/ko';

// One line stands in the middle of the 48 touch height; the box grows to four lines, then scrolls.
const MAX_HEIGHT = 48 + 24 * 3;
// react-native-web passes rows to its textarea; the React Native types do not know it.
const WEB_ONE_ROW = { rows: 1 } as object;

type KeyEvent = NativeSyntheticEvent<TextInputKeyPressEventData & { shiftKey?: boolean; isComposing?: boolean; keyCode?: number }>
  & { shiftKey?: boolean; preventDefault?: () => void };

// Enter sends and keeps the keyboard up; Shift+Enter is a new line; never while a Korean syllable is being put together.
export function InputBar({ partner, locked, text, onText, onSend }: {
  partner: string | null; locked: boolean; text: string; onText: (text: string) => void; onSend: (text: string) => void;
}) {
  const [focused, setFocused] = useState(false);
  const field = useRef<TextInput>(null);
  const ready = !locked && text.trim().length > 0;
  const send = () => ready && onSend(text.trim());
  const hint = partner ? ko.askTo(partner) : ko.say;
  // On web the field is a textarea: back to one row, then as tall as its words (scrollHeight never shrinks on its own).
  useLayoutEffect(() => {
    const el = field.current as unknown as HTMLTextAreaElement | null;
    if (!el?.style) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight + el.offsetHeight - el.clientHeight, MAX_HEIGHT)}px`;
  }, [text]);
  const onKey = (e: KeyEvent) => {
    const { key, isComposing, keyCode } = e.nativeEvent;
    if (key !== 'Enter' || e.shiftKey || e.nativeEvent.shiftKey || isComposing || keyCode === 229) return;
    e.preventDefault?.();
    send();
  };
  return (
    <View className="px-3 pb-2 pt-2">
      <View className={control({ kind: 'composer', tone: focused ? 'focus' : undefined, off: locked })}>
        <TextInput ref={field} {...WEB_ONE_ROW} value={text} onChangeText={onText} onKeyPress={onKey} editable={!locked} maxLength={200} multiline
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
          placeholder={hint} placeholderTextColor={colors.fg.subtle} accessibilityLabel={hint}
          enterKeyHint="send" submitBehavior="newline"
          style={{ outlineStyle: 'none' } as object}
          className={type({ kind: 'input' }, 'min-w-0 flex-1 py-3 pl-4 pr-1')} />
        <Pressable accessibilityRole="button" accessibilityLabel={ko.send} accessibilityState={{ disabled: !ready }}
          disabled={!ready} onPress={send} style={pressed} className="h-12 w-12 items-center justify-center">
          <Icon name="send" size={icon.md + 4} color={ready ? colors.gold.fg : colors.fg.subtle} width={2} />
        </Pressable>
      </View>
    </View>
  );
}
