import { View } from 'react-native';
import { Theme } from '@/constants/theme';
import { MenuButton } from './MenuButton';
import { ChipTab } from './ChipTab';
import { ShareButton } from './ShareButton';
import { PanelBody } from './PanelBody';
import type { PanelSlot } from '@/types/game';

export function ContextCard({ slots, activeId, onSelect, onNewGame }: {
  slots: PanelSlot[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewGame?: () => void;
}) {
  const activeSlot = slots.find(s => s.id === activeId) ?? null;
  const panel = activeSlot?.panel ?? null;

  return (
    <View style={{
      marginHorizontal: Theme.space.lg,
      backgroundColor: Theme.bgCard, borderWidth: 1, borderColor: Theme.border,
      borderRadius: Theme.radius.md,
    }}>
      <View style={{
        flexDirection: 'row', padding: 3, gap: 2, alignItems: 'center',
        borderBottomWidth: panel ? 1 : 0, borderBottomColor: Theme.border,
      }}>
        <MenuButton onNewGame={onNewGame} />
        <View style={{ flex: 1, flexDirection: 'row', gap: 2 }}>
          {slots.map(s => (
            <ChipTab key={s.id} chip={s.chip} active={s.id === activeId} onPress={() => onSelect(s.id)} />
          ))}
        </View>
        <ShareButton />
      </View>
      {panel && <PanelBody panel={panel} />}
    </View>
  );
}
