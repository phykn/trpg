import BottomSheet, {
  BottomSheetBackdrop, type BottomSheetBackdropProps, BottomSheetFooter, type BottomSheetFooterProps, BottomSheetView,
} from '@gorhom/bottom-sheet';
import { type ReactNode, useCallback, useRef, useState } from 'react';
import { View } from 'react-native';

import { colors, radius } from '@/design/tokens';
import { cn } from '@/design/ui';
import { SheetHeader } from './Sheet';
import { useDialog } from './useDialog';

const SNAPS = ['50%', '100%'];

// Every sheet (@gorhom/bottom-sheet). A long one opens halfway, so the chat above stays in view, and is pulled up to
// fill the screen; a short one (`fit`) is as tall as what it holds. Either is pulled down to close. The footer stays on
// the visible bottom edge. A list inside scrolls with BottomSheetScrollView, so dragging it first pulls the sheet up.
// Without onClose the sheet stays until something else replaces it.
export function DragSheet({ title, footer, full, fit, onClose, children }: {
  title: string; footer?: ReactNode; full?: boolean; fit?: boolean; onClose?: () => void; children: ReactNode;
}) {
  const sheet = useRef<BottomSheet>(null);
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
  return (
    <BottomSheet ref={sheet} index={fit ? 0 : start} snapPoints={fit ? undefined : SNAPS} enableDynamicSizing={fit === true}
      enablePanDownToClose={closes} enableContentPanningGesture={moves} enableHandlePanningGesture={moves}
      handleComponent={moves ? undefined : null}
      onClose={onClose} backdropComponent={backdrop} footerComponent={footer ? foot : undefined}
      backgroundStyle={{ backgroundColor: colors.canvas.floating, borderRadius: radius['2xl'], borderWidth: 1, borderColor: colors.border.strong }}
      handleIndicatorStyle={{ backgroundColor: colors.border.strong }}>
      <BottomSheetView style={fit ? undefined : { flex: 1 }}>
        <View ref={dialog} accessibilityRole={'dialog' as never} aria-modal
          className={fit ? cn('gap-3 px-4 pb-4', !moves && 'pt-3') : 'min-h-0 flex-1 gap-3 px-4'}>
          <SheetHeader title={title} onClose={closes ? close : undefined} />
          {children}
        </View>
      </BottomSheetView>
    </BottomSheet>
  );
}
