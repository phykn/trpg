import React from 'react';
import {
  View,
  TextInput,
  Keyboard,
  type NativeSyntheticEvent,
  type TextInputSubmitEditingEventData,
} from 'react-native';

import { colors, shadow } from '@/design/tokens';

import { DiceButton } from './DiceButton';
import { SendButton } from './SendButton';
import { StopButton } from './StopButton';

export function Composer({ input, setInput, onSend, onRoll, onStop, rolling, focused, rollEnabled, streaming }: {
  input: string;
  setInput: (text: string) => void;
  onSend: (text: string) => void;
  onRoll: () => void;
  onStop: () => void;
  rolling: boolean;
  focused: boolean;
  rollEnabled: boolean;
  streaming: boolean;
}) {
  // Mirror `input` into a ref so the keyboard-submit handler below can read
  // the latest text without waiting for React state to flush. handleChange
  // writes the ref synchronously; the effect catches parent-driven updates
  // (e.g. suggestion picks).
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

  // Keyboard "send" key. On Android Hangul IME, e.nativeEvent.text can
  // arrive pre-composition while onChangeText fires later with the final
  // composed text. Defer one tick and pick whichever string is longer
  // so the final character isn't dropped.
  const onNativeSubmit = (
    e: NativeSyntheticEvent<TextInputSubmitEditingEventData>,
  ) => {
    const fromEvent = e.nativeEvent.text ?? '';
    setTimeout(() => {
      const fromRef = inputRef.current ?? '';
      sendText(fromRef.length > fromEvent.length ? fromRef : fromEvent);
    }, 0);
  };
  const roll = () => {
    onRoll();
    Keyboard.dismiss();
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
        <DiceButton enabled={rollEnabled && !streaming} rolling={rolling} onPress={roll} />
        {streaming ? (
          <StopButton onPress={onStop} />
        ) : (
          <SendButton enabled={hasText} onPress={submit} />
        )}
      </View>
    </View>
  );
}
