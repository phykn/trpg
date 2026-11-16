import BottomSheet, {
  BottomSheetBackdrop, type BottomSheetBackdropProps, BottomSheetFooter, type BottomSheetFooterProps, BottomSheetView,
} from '@gorhom/bottom-sheet';
import { type ReactNode, useCallback, useRef, useState } from 'react';
import { View } from 'react-native';

import { colors, radius } from '@/design/tokens';
import { SheetHeader } from './Sheet';
import { useDialog } from './useDialog';

const SNAPS = ['50%', '100%'];

// A sheet that opens halfway, so the chat above stays in view, and is pulled up to fill the screen or down to close
// (@gorhom/bottom-sheet). The footer stays on the visible bottom edge at either height. A list inside scrolls with
// BottomSheetScrollView, so dragging it at half height first pulls the sheet up.
export function DragSheet({ title, footer, full, onClose, children }: {
  title: string; footer?: ReactNode; full?: boolean; onClose: () => void; children: ReactNode;
}) {
  const sheet = useRef<BottomSheet>(null);
  // `full` opens it at full height, for a line opened from elsewhere that has to be seen whole; it is read once.
  const [start] = useState(full ? 1 : 0);
  const close = useCallback(() => sheet.current?.close(), []);
  const dialog = useDialog(close);
  const backdrop = useCallback((props: BottomSheetBackdropProps) => (
    <BottomSheetBackdrop {...props} appearsOnIndex={0} disappearsOnIndex={-1} pressBehavior="close"
      opacity={0.5} style={[props.style, { backgroundColor: colors.fg.default }]} />
  ), []);
  const foot = useCallback((props: BottomSheetFooterProps) => (
    <BottomSheetFooter {...props}>
      <View className="bg-canvas-floating px-4 pb-4 pt-2">{footer}</View>
    </BottomSheetFooter>
  ), [footer]);
  return (
    <BottomSheet ref={sheet} index={start} snapPoints={SNAPS} enableDynamicSizing={false} enablePanDownToClose
      onClose={onClose} backdropComponent={backdrop} footerComponent={footer ? foot : undefined}
      backgroundStyle={{ backgroundColor: colors.canvas.floating, borderRadius: radius['2xl'], borderWidth: 1, borderColor: colors.border.strong }}
      handleIndicatorStyle={{ backgroundColor: colors.border.strong }}>
      <BottomSheetView style={{ flex: 1 }}>
        <View ref={dialog} accessibilityRole={'dialog' as never} aria-modal className="min-h-0 flex-1 gap-3 px-4">
          <SheetHeader title={title} onClose={close} />
          {children}
        </View>
      </BottomSheetView>
    </BottomSheet>
  );
}
