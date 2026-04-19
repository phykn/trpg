import React from 'react';
import { View, Text, Pressable, Modal } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Theme, typeStyle } from '@/constants/theme';

export function MenuButton({ onNewGame }: { onNewGame?: () => void }) {
  const [open, setOpen] = React.useState(false);

  return (
    <View style={{ flexShrink: 0 }}>
      <Pressable
        onPress={() => setOpen(!open)}
        style={{
          width: 30, height: 30, borderRadius: Theme.radius.sm,
          backgroundColor: open ? Theme.bgElev : 'transparent',
          alignItems: 'center', justifyContent: 'center',
        }}
      >
        <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={Theme.textDim} strokeWidth={1.8} strokeLinecap="round">
          <Path d="M4 7h16M4 12h16M4 17h16" />
        </Svg>
      </Pressable>
      <Modal transparent visible={open} onRequestClose={() => setOpen(false)} animationType="fade">
        <Pressable style={{ flex: 1 }} onPress={() => setOpen(false)}>
          <View style={{
            position: 'absolute', top: 80, left: 20, minWidth: 180,
            backgroundColor: Theme.bgCard, borderWidth: 1, borderColor: Theme.border,
            borderRadius: Theme.radius.sm, padding: 4,
            shadowColor: '#2D2A26', shadowOpacity: 0.08, shadowRadius: 24, shadowOffset: { width: 0, height: 8 }, elevation: 4,
          }}>
            <Pressable
              onPress={() => { setOpen(false); onNewGame?.(); }}
              style={{
                flexDirection: 'row', alignItems: 'center', gap: 10,
                paddingVertical: 8, paddingHorizontal: 10, borderRadius: 8,
              }}
            >
              <Svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke={Theme.textDim} strokeWidth={1.8} strokeLinecap="round">
                <Path d="M12 5v14M5 12h14" />
              </Svg>
              <Text style={{ ...typeStyle('body'), color: Theme.text, fontFamily: Theme.fonts.sansRegular }}>
                새 게임 시작
              </Text>
            </Pressable>
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}
