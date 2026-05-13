import { TextInput } from 'react-native';

import { colors } from '@/design/tokens';

type Props = {
  value: string;
  onChangeText: (v: string) => void;
  placeholder: string;
};

export function Input({ value, onChangeText, placeholder }: Props) {
  return (
    <TextInput
      value={value}
      onChangeText={onChangeText}
      placeholder={placeholder}
      placeholderTextColor={colors.fg.subtle}
      className="h-10 px-3 rounded-sm bg-canvas-inset border border-border-default font-sans text-body text-fg-default"
      style={{ borderWidth: 1, textAlign: 'center' }}
    />
  );
}
