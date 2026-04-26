import { View } from 'react-native';
import { colors } from '@/design/tokens';

type Props = {
  value: number;
  max: number;
  color: string;
  h?: number;
  signed?: boolean;
};

export function Bar({ value, max, color, h = 4, signed = false }: Props) {
  // max=0 happens at max-level (expMax=0). Render an empty bar instead of NaN%.
  if (max <= 0) {
    return (
      <View
        className="w-full bg-canvas-inset rounded-full overflow-hidden"
        style={{ height: h }}
      />
    );
  }
  if (signed) {
    const clamped = Math.max(-max, Math.min(max, value));
    const magPct = (Math.abs(clamped) / max) * 50;
    const fillPositioning = clamped >= 0 ? { left: '50%' as const } : { right: '50%' as const };
    return (
      <View
        className="w-full bg-canvas-inset rounded-full overflow-hidden"
        style={{ height: h }}
      >
        <View
          className="absolute inset-y-0"
          style={{ width: `${magPct}%`, backgroundColor: color, ...fillPositioning }}
        />
        <View
          className="absolute inset-y-0 left-1/2"
          style={{ width: 1, marginLeft: -0.5, backgroundColor: colors.fg.muted }}
        />
      </View>
    );
  }
  const pct = Math.max(0, Math.min(1, value / max)) * 100;
  return (
    <View
      className="w-full bg-canvas-inset rounded-full overflow-hidden"
      style={{ height: h }}
    >
      <View
        className="h-full rounded-full"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </View>
  );
}
