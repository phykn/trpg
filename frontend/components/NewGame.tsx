import React from 'react';
import {
  ActivityIndicator,
  Keyboard,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';

import { colors } from '@/design/tokens';
import { listProfiles } from '@/services';
import type { InitRequest, ProfileCard, RaceCard } from '@/types/wire';

type Props = {
  onSubmit: (body: InitRequest) => Promise<void>;
};

export function NewGame({ onSubmit }: Props) {
  const [profiles, setProfiles] = React.useState<ProfileCard[] | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);

  const [profileId, setProfileId] = React.useState<string | null>(null);
  const [raceId, setRaceId] = React.useState<string | null>(null);
  const [name, setName] = React.useState('');
  const [appearance, setAppearance] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  const loadProfiles = React.useCallback(() => {
    setLoadError(null);
    setProfiles(null);
    listProfiles()
      .then((list) => {
        setProfiles(list);
        if (list.length === 1) setProfileId(list[0].id);
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
    setSubmitError(null);
    try {
      await onSubmit({
        profile: profileId,
        player: { name: trimmedName, race_id: raceId, appearance: trimmedAppearance },
      });
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  };

  if (loadError) {
    return (
      <CenterMessage>
        <Text className="font-sans text-body text-danger-fg mb-3">{loadError}</Text>
        <Pressable
          onPress={loadProfiles}
          className="px-4 h-9 rounded-md bg-canvas-inset border border-border-default items-center justify-center"
        >
          <Text className="font-sans-medium text-body text-fg-default">다시 시도</Text>
        </Pressable>
      </CenterMessage>
    );
  }

  if (!profiles) {
    return (
      <CenterMessage>
        <ActivityIndicator color={colors.accent.fg} />
      </CenterMessage>
    );
  }

  return (
    <ScrollView
      className="flex-1 bg-canvas-default"
      contentContainerClassName="px-5 py-8 gap-7"
      keyboardShouldPersistTaps="handled"
    >
      <View className="gap-1">
        <Text className="font-serif-medium text-lead text-fg-default">새 게임</Text>
        <Text className="font-sans text-body text-fg-muted">
          세계관과 종족을 고르고, 이름·외모를 채우면 시작합니다.
        </Text>
      </View>

      <Section label="세계관">
        {profiles.map((p) => (
          <SelectCard
            key={p.id}
            title={p.name}
            description={p.description}
            selected={profileId === p.id}
            onPress={() => {
              setProfileId(p.id);
              setRaceId(null);
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

      {submitError && (
        <Text className="font-sans text-body text-danger-fg">{submitError}</Text>
      )}

      <Pressable
        onPress={submit}
        disabled={!canSubmit}
        className={`h-12 rounded-md items-center justify-center ${
          canSubmit ? 'bg-accent-fg' : 'bg-canvas-inset border border-border-default'
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
    </ScrollView>
  );
}

function CenterMessage({ children }: { children: React.ReactNode }) {
  return (
    <View className="flex-1 bg-canvas-default items-center justify-center px-5 gap-2">
      {children}
    </View>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View className="gap-2">
      <Text
        className="font-mono-semibold text-panel text-fg-subtle uppercase"
        style={{ letterSpacing: 1.2 }}
      >
        {label}
      </Text>
      <View className="gap-2">{children}</View>
    </View>
  );
}

function SelectCard({
  title,
  description,
  selected,
  onPress,
}: {
  title: string;
  description?: string;
  selected: boolean;
  onPress: () => void;
}) {
  const bg = selected ? 'bg-accent-muted border-accent-fg' : 'bg-canvas-subtle border-border-default';
  return (
    <Pressable
      onPress={onPress}
      className={`px-4 py-3 rounded-md border ${bg}`}
      style={{ borderWidth: 1.5 }}
    >
      <Text
        className={`font-sans-semibold text-title ${
          selected ? 'text-accent-fg' : 'text-fg-default'
        }`}
      >
        {title}
      </Text>
      {description ? (
        <Text className="font-sans text-body text-fg-muted mt-1">{description}</Text>
      ) : null}
    </Pressable>
  );
}

function Input({
  value,
  onChangeText,
  placeholder,
}: {
  value: string;
  onChangeText: (v: string) => void;
  placeholder: string;
}) {
  return (
    <TextInput
      value={value}
      onChangeText={onChangeText}
      placeholder={placeholder}
      placeholderTextColor={`${colors.fg.default}55`}
      className="h-11 px-3 rounded-md bg-canvas-subtle border border-border-default font-sans text-body text-fg-default"
      style={{ borderWidth: 1 }}
    />
  );
}
