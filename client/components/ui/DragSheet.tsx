import BottomSheet, {
  BottomSheetBackdrop, type BottomSheetBackdropProps, BottomSheetFooter, type BottomSheetFooterProps, BottomSheetView,
} from '@gorhom/bottom-sheet';
import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react';
import { View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue } from 'react-native-reanimated';

import { colors, radius } from '@/design/tokens';
import { cn } from '@/design/ui';
import { SheetHeader } from './Sheet';
import { useDialog } from './useDialog';

const SNAPS = ['50%', '100%'];

// A long sheet opens halfway so the chat above stays in view; a short one (`fit`) is as tall as what it holds.
// Without onClose it stays until something else replaces it; `shut` closes it from outside, sliding down.
export function DragSheet({ title, footer, full, fit, shut, onClose, children }: {
  title: string; footer?: ReactNode; full?: boolean; fit?: boolean; shut?: boolean; onClose?: () => void; children: ReactNode;
}) {
  const sheet = useRef<BottomSheet>(null);
  useEffect(() => {
    if (shut) sheet.current?.close();
  }, [shut]);
  // `full` opens it at full height, for a line opened from elsewhere that has to be seen whole; it is read once.
  const [start] = useState(full ? 1 : 0);
  const close = useCallback(() => sheet.current?.close(), []);
  const closes = onClose !== undefined;
  // A short sheet that cannot close has nowhere to be dragged, so it shows no handle.
  const moves = closes || !fit;
  const dialog = useDialog(closes ? close : undefined);
  const backdrop = useCallback((props: BottomSheetBackdropProps) => (
    <BottomSheetBackdrop {...props} appearsOnIndex={0} disappearsOnIndex={-1} pressBehavior={closes ? 'close' : 'none'}
      opacity={1} style={[props.style, { backgroundColor: colors.overlay }]} />
  ), [closes]);
  const foot = useCallback((props: BottomSheetFooterProps) => (
    <BottomSheetFooter {...props}>
      <View className="bg-canvas-floating px-4 pb-4 pt-2">{footer}</View>
    </BottomSheetFooter>
  ), [footer]);
  // A long sheet's body ends at the screen's edge whatever the snap, so its list scrolls to the last line;
  // the sheet sits `position` below the top, and that much of it is below the screen.
  const position = useSharedValue(0);
  const visible = useAnimatedStyle(() => ({ flex: 1, paddingBottom: position.value }));
  const body = (
    <View ref={dialog} accessibilityRole={'dialog' as never} aria-modal
      className={fit ? cn('gap-3 px-4 pb-4', !moves && 'pt-3') : 'min-h-0 flex-1 gap-3 px-4'}>
      <SheetHeader title={title} onClose={closes ? close : undefined} />
      {children}
    </View>
  );
  return (
    <BottomSheet ref={sheet} index={fit ? 0 : start} snapPoints={fit ? undefined : SNAPS} enableDynamicSizing={fit === true}
      enablePanDownToClose={closes} enableContentPanningGesture={moves} enableHandlePanningGesture={moves}
      handleComponent={moves ? undefined : null}
      animatedPosition={position} onClose={onClose} backdropComponent={backdrop} footerComponent={footer ? foot : undefined}
      backgroundStyle={{ backgroundColor: colors.canvas.floating, borderRadius: radius['2xl'], borderWidth: 1, borderColor: colors.border.strong }}
      handleIndicatorStyle={{ backgroundColor: colors.border.strong }}>
      {fit ? <BottomSheetView>{body}</BottomSheetView> : <Animated.View style={visible}>{body}</Animated.View>}
    </BottomSheet>
  );
}
