import { ArrowRight, ArrowUp, BookOpen, ChevronRight, Eye, Flag, RotateCcw, X } from 'lucide-react-native';

// Lucide's one stroke set, so every icon has the same weight and optical size.
const ICONS = {
  flag: Flag,
  eye: Eye,
  arrow: ArrowRight,
  send: ArrowUp,
  close: X,
  next: ChevronRight,
  retry: RotateCcw,
  book: BookOpen,
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, size, color, width = 1.8 }: { name: IconName; size: number; color: string; width?: number }) {
  const Shape = ICONS[name];
  return <Shape size={size} color={color} strokeWidth={width} />;
}
