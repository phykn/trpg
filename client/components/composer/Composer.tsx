import React from 'react';
import {
  View,
  TextInput,
  Keyboard,
  type NativeSyntheticEvent,
  type TextInputSubmitEditingEventData,
} from 'react-native';

import { colors, shadow } from '@/design/tokens';

import { SendButton } from './SendButton';
import { StopButton } from './StopButton';

export function Composer({ input, setInput, onSend, onStop, focused, streaming }: {
  input: string;
  setInput: (text: string) => void;
  onSend: (text: string) => void;
  onStop: () => void;
  focused: boolean;
  streaming: boolean;
}) {
  const inputRef = React.useRef(input);
  React.useEffect(() => { inputRef.current = input; }, [input]);

  const handleChange = (t: string) => {
    inputRef.current = t;
    setInput(t);
  };

  const trimmed = input.trim();
  const hasText = trimmed.length > 0;

  const sendText = (raw: string) => {
    const text = raw.trim();
    if (!text) return;
    onSend(text);
    inputRef.current = '';
    setInput('');
    Keyboard.dismiss();
  };

  const submit = () => sendText(inputRef.current);

  // Android Hangul IME fires SubmitEditing pre-composition; defer one tick
  // and take whichever of nativeEvent.text / inputRef is longer.
  const onNativeSubmit = (
    e: NativeSyntheticEvent<TextInputSubmitEditingEventData>,
  ) => {
    const fromEvent = e.nativeEvent.text ?? '';
    setTimeout(() => {
      const fromRef = inputRef.current ?? '';
      sendText(fromRef.length > fromEvent.length ? fromRef : fromEvent);
    }, 0);
  };

  const borderClass = focused ? 'border-accent-fg' : 'border-border-default';

  return (
    <View
      className={`mx-5 mt-1.5 bg-canvas-subtle rounded-md p-2 border ${borderClass}`}
      style={shadow.paper}
    >
      <TextInput
        value={input}
        onChangeText={handleChange}
        onSubmitEditing={onNativeSubmit}
        placeholder="무엇을 하시겠습니까?"
        placeholderTextColor={`${colors.fg.default}55`}
        returnKeyType="send"
        multiline
        submitBehavior="blurAndSubmit"
        className="font-sans text-title px-2 pt-2 text-fg-default"
        style={{ paddingBottom: 6, maxHeight: 140 }}
      />
      <View className="flex-row items-center justify-end gap-2 px-1 pt-1">
        {streaming ? (
          <StopButton onPress={onStop} />
        ) : (
          <SendButton enabled={hasText} onPress={submit} />
        )}
      </View>
    </View>
  );
}
