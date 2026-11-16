import {
  BookOpen, ChevronRight, Clock, Dumbbell, Eye, Heart, Lightbulb, MapPin, MessageCircle, Package, Play, RotateCcw, Scale,
  Send, Settings, User, Wrench, X,
} from 'lucide-react-native';

// Lucide's one stroke set, so every icon has the same weight and optical size.
// One icon per idea, used for it everywhere: the place pin on the bar, the move button and the places tab alike.
const ICONS = {
  eye: Eye, // looking around, and what was seen
  place: MapPin,
  person: User,
  item: Package,
  heard: MessageCircle, // what people said, and a topic
  book: BookOpen, // the notebook
  clock: Clock,
  conclude: Scale,
  settings: Settings,
  send: Send,
  close: X,
  next: ChevronRight,
  retry: RotateCcw, // asking again, and a new game
  step: Play, // a filled triangle; turned around it steps down
  charm: Heart, // the four stats
  might: Dumbbell,
  wit: Lightbulb,
  skill: Wrench,
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, size, color, width = 1.8, fill, flip }: {
  name: IconName; size: number; color: string; width?: number; fill?: boolean; flip?: boolean;
}) {
  const Shape = ICONS[name];
  return (
    <Shape size={size} color={color} strokeWidth={width} fill={fill ? color : 'none'}
      style={flip ? { transform: [{ rotate: '180deg' }] } : undefined} />
  );
}
