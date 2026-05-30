import React from 'react';
import {
  ActivityIndicator,
  Keyboard,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';

import { CenterMessage, ErrorState, Surface } from '@/components/ui';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { errorMessageForDisplay } from '@/logic/game/errors';
import { getVersion, listProfiles } from '@/services';
import type { InitRequest, ProfileCard, RaceCard } from '@/services/wire';

import { Input } from './Input';
import { Section } from './Section';
import { SelectCard } from './SelectCard';

const CLIENT_SHA = process.env.EXPO_PUBLIC_GIT_SHA ?? 'local';

type Props = {
  onSubmit: (body: InitRequest) => Promise<void>;
};

export function NewGame({ onSubmit }: Props) {
  const [profiles, setProfiles] = React.useState<ProfileCard[] | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);

  const [profileId, setProfileId] = React.useState<string | null>(null);
  const [raceId, setRaceId] = React.useState<string | null>(null);
  const [gender, setGender] = React.useState<'male' | 'female'>('male');
  const [name, setName] = React.useState<string>(ko.newGame.defaultName);
  const [submitting, setSubmitting] = React.useState(false);
  const [serverSha, setServerSha] = React.useState<string>('?');

  React.useEffect(() => {
    getVersion()
      .then((v) => setServerSha(v.sha))
      .catch(() => setServerSha('?'));
  }, []);

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
        setLoadError(errorMessageForDisplay(e));
      });
  }, []);

  React.useEffect(loadProfiles, [loadProfiles]);

  const selectedProfile = profiles?.find((p) => p.id === profileId) ?? null;
  const races = selectedProfile?.races ?? [];

  const trimmedName = name.trim();
  const canSubmit = !!profileId && !!raceId && !!trimmedName && !submitting;

  const submit = async () => {
    if (!canSubmit || !profileId || !raceId) return;
    Keyboard.dismiss();
    setSubmitting(true);
    try {
      await onSubmit({
        profile: profileId,
        player: { name: trimmedName, race_id: raceId, gender },
        locale: 'ko',
      });
    } finally {
      setSubmitting(false);
    }
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
          {ko.newGame.noProfiles}
        </Text>
      </CenterMessage>
    );
  }

  return (
    <ScrollView
      className="flex-1 bg-canvas-default"
      contentContainerClassName="px-4 py-5"
      keyboardShouldPersistTaps="handled"
    >
      <Surface variant="floating" className="bg-canvas-default px-4 py-4 gap-5">
        <View className="gap-2 pb-4">
          <Text className="font-mono text-meta text-accent-fg uppercase">
            CHARACTER · NEW
          </Text>
          <Text className="font-serif-medium text-narration text-fg-default">{ko.menu.newGame}</Text>
          <Text className="font-sans text-body text-fg-muted">
            {ko.newGame.hint}
          </Text>
        </View>

        <Section label={ko.form.name}>
          <Input value={name} onChangeText={setName} placeholder={ko.newGame.namePlaceholder} />
        </Section>

        <Section label={ko.form.gender}>
          <View className="flex-row gap-2">
            <View className="flex-1">
              <SelectCard
                title={ko.newGame.male}
                selected={gender === 'male'}
                onPress={() => setGender('male')}
                dense
              />
            </View>
            <View className="flex-1">
              <SelectCard
                title={ko.newGame.female}
                selected={gender === 'female'}
                onPress={() => setGender('female')}
                dense
              />
            </View>
          </View>
        </Section>

        <Section label={ko.form.world}>
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
          <Section label={ko.form.race}>
            {races.length === 0 ? (
              <Text className="font-sans text-body text-fg-muted">{ko.newGame.noRaces}</Text>
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

        <Section label={ko.form.language}>
          <SelectCard
            title={ko.newGame.korean}
            selected
            onPress={() => {}}
            dense
          />
        </Section>

        <Pressable
          onPress={submit}
          disabled={!canSubmit}
          accessibilityRole="button"
          accessibilityLabel={ko.action.start}
          accessibilityState={{ disabled: !canSubmit }}
          className={`h-10 rounded-sm items-center justify-center ${
            canSubmit ? 'bg-accent-fg active:opacity-80' : 'bg-canvas-inset border border-border-default'
          }`}
        >
          <Text
            className={`font-sans-semibold text-title ${
              canSubmit ? 'text-fg-on-emphasis' : 'text-fg-subtle'
            }`}
          >
            {submitting ? ko.newGame.creating : ko.action.start}
          </Text>
        </Pressable>

        <View className="items-center pt-2">
          <Text className="font-mono text-meta text-fg-subtle">
            client: {CLIENT_SHA}  ·  server: {serverSha}
          </Text>
        </View>
      </Surface>
    </ScrollView>
  );
}
