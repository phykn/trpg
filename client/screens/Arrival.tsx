import { useState } from 'react';
import { Text, TextInput, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { PagedList } from '@/components/ui/PagedList';
import { Reader } from '@/components/ui/Reader';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameCatalog } from '@/services/types';

type Props = {
  catalog: GameCatalog;
  busy: boolean;
  canResume: boolean;
  onStart: (name: string, role: string) => Promise<void>;
  onResume: () => void;
};

export function Arrival({ catalog, busy, canResume, onStart, onResume }: Props) {
  const [name, setName] = useState(ko.defaultName);
  const [step, setStep] = useState<'intro' | 'name' | 'roles'>('intro');
  const [role, setRole] = useState<string | null>(null);
  const selected = catalog.roles.find((item) => item.id === role);
  return (
    <View className="flex-1 min-h-0 px-6 pb-5 pt-6 gap-5">
      <View className="flex-row items-center gap-3">
        {step !== 'intro' ? <Button label={ko.back} disabled={busy} onPress={() => role ? setRole(null) : setStep(step === 'roles' ? 'name' : 'intro')} /> : null}
        <Text accessibilityRole="header" className="flex-1 font-sans-semibold text-scene text-fg-default">{step === 'intro' ? catalog.title : step === 'name' ? ko.name : selected?.name ?? ko.role}</Text>
      </View>
      {step === 'intro' ? <Reader text={catalog.synopsis + '\n\n' + ko.readHelp} doneLabel={ko.prepare} onDone={() => setStep('name')} /> : null}
      {step === 'name' ? (
        <View className="flex-1 min-h-0 gap-4">
          <TextInput accessibilityLabel={ko.name} value={name} onChangeText={setName} maxLength={20} editable={!busy} placeholder={ko.defaultName} placeholderTextColor={colors.fg.subtle} returnKeyType="done" onSubmitEditing={() => { if (name.trim()) setStep('roles'); }} className="min-h-14 rounded-lg border border-border-strong bg-canvas-subtle px-4 py-3 font-sans text-lead text-fg-default" />
          <View className="flex-1" />
          <Button label={ko.chooseRole} primary disabled={!name.trim() || busy} onPress={() => setStep('roles')} />
        </View>
      ) : null}
      {step === 'roles' && !selected ? <PagedList entries={catalog.roles.map((item) => ({ id: item.id, label: item.name, meta: item.text }))} onSelect={setRole} disabled={busy} /> : null}
      {selected ? <Reader key={selected.id} text={selected.text + (canResume ? '\n\n' + ko.newGameHelp : '')} doneLabel={ko.start} disabled={busy} onDone={() => void onStart(name.trim(), selected.id)} /> : null}
      {canResume && step === 'intro' ? <Button label={ko.resume} disabled={busy} onPress={onResume} /> : null}
    </View>
  );
}
