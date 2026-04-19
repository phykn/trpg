import { Text } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';

export function GMNarration({ text }: { text: string }) {
  return (
    <Text style={{
      fontFamily: Theme.fonts.serifRegular, color: Theme.text,
      ...typeStyle('lead'),
    }}>{text}</Text>
  );
}
