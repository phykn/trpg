import React from 'react';
import { View, TextInput } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';
import { DiceButton } from './DiceButton';
import { SendButton } from './SendButton';

export function Composer({ onSend, onRoll, rolling, focused, onFocus, onBlur, rollEnabled }: {
  onSend: (text: string) => void;
  onRoll: () => void;
  rolling: boolean;
  focused: boolean;
  onFocus: () => void;
  onBlur: () => void;
  rollEnabled: boolean;
}) {
  const [input, setInput] = React.useState('');
  const submit = () => {
    const t = input.trim();
    if (!t) return;
    onSend(t);
    setInput('');
  };
  const hasText = input.trim().length > 0;

  return (
    <View style={{
      marginTop: 6, marginHorizontal: Theme.space.lg,
      backgroundColor: Theme.bgCard,
      borderWidth: 1.5, borderColor: focused ? Theme.accent : Theme.border,
      borderRadius: Theme.radius.lg + 6, padding: Theme.space.sm,
      shadowColor: Theme.accent,
      shadowOpacity: focused ? 0.15 : 0,
      shadowRadius: focused ? 8 : 0,
      shadowOffset: { width: 0, height: 0 },
    }}>
      <TextInput
        value={input}
        onChangeText={setInput}
        onSubmitEditing={submit}
        onFocus={onFocus}
        onBlur={onBlur}
        placeholder="무엇을 하시겠습니까?"
        placeholderTextColor={`${Theme.text}55`}
        returnKeyType="send"
        style={{
          color: Theme.text,
          fontFamily: Theme.fonts.sansRegular,
          ...typeStyle('title', { fontWeight: '400' as const }),
          paddingHorizontal: Theme.space.sm,
          paddingTop: Theme.space.sm, paddingBottom: 6,
        }}
      />
      <View style={{
        flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
        paddingHorizontal: 4, paddingTop: 4,
      }}>
        <DiceButton enabled={rollEnabled} rolling={rolling} onPress={onRoll} />
        <SendButton enabled={hasText} onPress={submit} />
      </View>
    </View>
  );
}
