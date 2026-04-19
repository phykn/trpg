import { Text } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';

export function ActDivider({ text }: { text: string }) {
  return (
    <Text style={{
      color: Theme.textFaint, fontFamily: Theme.fonts.monoRegular,
      ...typeStyle('body', { fontStyle: 'italic' }),
      textAlign: 'center', paddingHorizontal: Theme.space.xl,
    }}>— {text} —</Text>
  );
}
