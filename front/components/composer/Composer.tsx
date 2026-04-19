import React from 'react';
import { View, TextInput, Keyboard } from 'react-native';
import { colors } from '@/design/tokens';
import { DiceButton } from './DiceButton';
import { SendButton } from './SendButton';
import { StopButton } from './StopButton';

export function Composer({ onSend, onRoll, onStop, rolling, focused, rollEnabled, streaming }: {
  onSend: (text: string) => void;
  onRoll: () => void;
  onStop: () => void;
  rolling: boolean;
  focused: boolean;
  rollEnabled: boolean;
  streaming: boolean;
}) {
  const [input, setInput] = React.useState('');

  const submit = () => {
    const t = input.trim();
    if (!t) return;
    onSend(t);
    setInput('');
    Keyboard.dismiss();
  };
  const roll = () => {
    onRoll();
    Keyboard.dismiss();
  };
  const hasText = input.trim().length > 0;

  const borderClass = focused ? 'border-accent-fg' : 'border-border-default';

  return (
    <View
      className={`mx-5 mt-1.5 bg-canvas-subtle rounded-xl p-2 ${borderClass}`}
      style={{
        borderWidth: 1.5,
        shadowColor: colors.accent.fg,
        shadowOpacity: focused ? 0.15 : 0,
        shadowRadius: focused ? 8 : 0,
        shadowOffset: { width: 0, height: 0 },
      }}
    >
      <TextInput
        value={input}
        onChangeText={setInput}
        onSubmitEditing={submit}
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
