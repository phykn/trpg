import React from 'react';
import {
  ActivityIndicator,
  Keyboard,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';

import { CenterMessage, ErrorState } from '@/components/ui';
import { colors } from '@/design/tokens';
import { listProfiles } from '@/services';
import type { InitRequest, ProfileCard, RaceCard } from '@/types/wire';

import { Input } from './Input';
import { Section } from './Section';
import { SelectCard } from './SelectCard';

type Props = {
  onSubmit: (body: InitRequest) => Promise<void>;
};

export function NewGame({ onSubmit }: Props) {
  const [profiles, setProfiles] = React.useState<ProfileCard[] | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);

  const [profileId, setProfileId] = React.useState<string | null>(null);
  const [raceId, setRaceId] = React.useState<string | null>(null);
  const [name, setName] = React.useState('주인공');
  const [appearance, setAppearance] = React.useState('평범함');
  const [submitting, setSubmitting] = React.useState(false);

  const loadProfiles = React.useCallback(() => {
    setLoadError(null);
    setProfiles(null);
    listProfiles()
      .then((list) => {
        setProfiles(list);
        if (list.length === 1) {
          setProfileId(list[0].id);
          setRaceId(list[0].races[0]?.id ?? null);
        }
      })
      .catch((e: unknown) => {
        setLoadError(e instanceof Error ? e.message : String(e));
      });
  }, []);

  React.useEffect(loadProfiles, [loadProfiles]);

  const selectedProfile = profiles?.find((p) => p.id === profileId) ?? null;
  const races = selectedProfile?.races ?? [];

  const trimmedName = name.trim();
  const trimmedAppearance = appearance.trim();
  const canSubmit =
    !!profileId && !!raceId && !!trimmedName && !!trimmedAppearance && !submitting;

  const submit = async () => {
    if (!canSubmit || !profileId || !raceId) return;
    Keyboard.dismiss();
    setSubmitting(true);
    await onSubmit({
      profile: profileId,
      player: { name: trimmedName, race_id: raceId, appearance: trimmedAppearance },
    });
  };

  if (loadError) {
    return <ErrorState message={loadError} onRetry={loadProfiles} />;
  }

  if (!profiles) {
    return (
      <CenterMessage>
        <ActivityIndicator color={colors.accent.fg} />
      </CenterMessage>
    );
  }

  if (profiles.length === 0) {
    return (
      <CenterMessage>
        <Text className="font-sans text-body text-fg-muted">
          선택 가능한 시나리오가 없습니다.
        </Text>
      </CenterMessage>
    );
  }

  return (
    <ScrollView
      className="flex-1 bg-canvas-default"
      contentContainerClassName="px-5 py-6 gap-6"
      keyboardShouldPersistTaps="handled"
    >
      <View className="gap-2">
        <View className="flex-row items-center gap-2.5">
          <Text
            className="font-sans-semibold text-meta text-accent-fg"
            style={{ letterSpacing: 1.2 }}
          >
            캐릭터 생성
          </Text>
          <View style={{ flex: 1, height: 1, backgroundColor: colors.border.default }} />
          <Text style={{ color: colors.accent.fg, fontSize: 10 }}>◇</Text>
        </View>
        <Text className="font-serif-medium text-narration text-fg-default">새 게임</Text>
        <Text className="font-sans text-body text-fg-muted">
          세계관과 종족을 고르고, 이름·외모를 채우면 시작합니다.
        </Text>
      </View>

      <Pressable
        onPress={submit}
        disabled={!canSubmit}
        className={`h-10 rounded-md items-center justify-center ${
          canSubmit ? 'bg-accent-fg active:opacity-80' : 'bg-canvas-inset border border-border-default'
        }`}
      >
        <Text
          className={`font-sans-semibold text-title ${
            canSubmit ? 'text-fg-on-emphasis' : 'text-fg-subtle'
          }`}
        >
          {submitting ? '생성 중…' : '시작'}
        </Text>
      </Pressable>

      <Section label="세계관">
        {profiles.map((p) => (
          <SelectCard
            key={p.id}
            title={p.name}
            description={p.description}
            selected={profileId === p.id}
            onPress={() => {
              setProfileId(p.id);
              setRaceId(p.races[0]?.id ?? null);
            }}
          />
        ))}
      </Section>

      {selectedProfile && (
        <Section label="종족">
          {races.length === 0 ? (
            <Text className="font-sans text-body text-fg-muted">선택 가능한 종족이 없습니다.</Text>
          ) : (
            races.map((r: RaceCard) => (
              <SelectCard
                key={r.id}
                title={r.name}
                description={r.description}
                selected={raceId === r.id}
                onPress={() => setRaceId(r.id)}
              />
            ))
          )}
        </Section>
      )}

      <Section label="이름">
        <Input value={name} onChangeText={setName} placeholder="등장인물의 이름" />
      </Section>

      <Section label="외모">
        <Input
          value={appearance}
          onChangeText={setAppearance}
          placeholder="한 줄로 외모를 묘사"
        />
      </Section>
    </ScrollView>
  );
}
