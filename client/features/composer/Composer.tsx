import React from 'react';
import {
  View,
  TextInput,
  Keyboard,
  Platform,
  type NativeSyntheticEvent,
  type TextInputContentSizeChangeEventData,
  type TextInputSubmitEditingEventData,
} from 'react-native';

import { colors, shadow } from '@/design/tokens';

import { SendButton } from './SendButton';
import { StopButton } from './StopButton';
import { ThinkToggle } from './ThinkToggle';

const INPUT_MIN_HEIGHT = 40;
const INPUT_MAX_HEIGHT = 320;
const IS_WEB = Platform.OS === 'web';

export function Composer({ input, setInput, onSend, onStop, streaming, think, onToggleThink, locked = false }: {
  input: string;
  setInput: (text: string) => void;
  onSend: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  locked?: boolean;
  think: boolean;
  onToggleThink: () => void;
}) {
  const inputRef = React.useRef(input);
  React.useEffect(() => { inputRef.current = input; }, [input]);

  const textInputRef = React.useRef<TextInput>(null);
  const [inputHeight, setInputHeight] = React.useState(INPUT_MIN_HEIGHT);

  // RN-web's onContentSizeChange doesn't fire on shrink — measure scrollHeight after collapsing to 0.
  React.useLayoutEffect(() => {
    if (!IS_WEB) return;
    const node = textInputRef.current as unknown as HTMLTextAreaElement | null;
    if (!node) return;
    node.style.height = '0px';
    const next = Math.min(
      INPUT_MAX_HEIGHT,
      Math.max(INPUT_MIN_HEIGHT, node.scrollHeight),
    );
    node.style.height = `${next}px`;
    setInputHeight((prev) => (prev === next ? prev : next));
  }, [input]);

  const handleChange = (t: string) => {
    inputRef.current = t;
    setInput(t);
  };

  const trimmed = input.trim();
  const hasText = trimmed.length > 0 && !locked;

  const sendText = (raw: string) => {
    const text = raw.trim();
    if (!text) return;
    onSend(text);
    inputRef.current = '';
    setInput('');
    setInputHeight(INPUT_MIN_HEIGHT);
    Keyboard.dismiss();
  };

  const submit = () => sendText(inputRef.current);

  const onNativeSubmit = (
    e: NativeSyntheticEvent<TextInputSubmitEditingEventData>,
  ) => {
    const fromEvent = e.nativeEvent.text ?? '';
    setTimeout(() => {
      const fromRef = inputRef.current ?? '';
      sendText(fromRef.length > fromEvent.length ? fromRef : fromEvent);
    }, 0);
  };

  const onContentSizeChange = (
    e: NativeSyntheticEvent<TextInputContentSizeChangeEventData>,
  ) => {
    if (IS_WEB) return;
    const next = Math.min(
      INPUT_MAX_HEIGHT,
      Math.max(INPUT_MIN_HEIGHT, e.nativeEvent.contentSize.height),
    );
    setInputHeight(next);
  };

  return (
    <View
      className="mx-5 mt-1.5 bg-canvas-subtle rounded-xl px-3 pt-2 pb-2 gap-1"
      style={shadow.floating}
    >
      <TextInput
        ref={textInputRef}
        value={input}
        onChangeText={handleChange}
        onSubmitEditing={onNativeSubmit}
        onContentSizeChange={onContentSizeChange}
        editable={!locked}
        accessibilityState={{ disabled: locked }}
        placeholder={locked ? '판정을 먼저 굴려주세요' : '무엇을 하시겠습니까?'}
        placeholderTextColor={`${colors.fg.default}55`}
        returnKeyType="send"
        multiline
        submitBehavior="blurAndSubmit"
        textAlignVertical="top"
        className="font-sans text-title text-fg-default"
        // Cast: web-only CSS (outlineStyle, scrollbarWidth) is passed through by RN-web but absent from TextStyle.
        style={{
          paddingTop: 8,
          paddingBottom: 8,
          height: inputHeight,
          // Kill RN-web's textarea border + Chrome focus ring so the composer reads as a flat chat input.
          borderWidth: 0,
          outlineWidth: 0,
          outlineStyle: 'none',
          backgroundColor: 'transparent',
          // Hide RN-web textarea scrollbar; wheel/keys still scroll overflow.
          ...(IS_WEB ? { scrollbarWidth: 'none' } : null),
        } as object}
      />
      <View className="flex-row items-center justify-between">
        <ThinkToggle think={think} onToggle={onToggleThink} />
        {streaming ? (
          <StopButton onPress={onStop} />
        ) : (
          <SendButton enabled={hasText} onPress={submit} />
        )}
      </View>
    </View>
  );
}
