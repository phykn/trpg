import React from 'react';
import { ActivityIndicator, Text } from 'react-native';

import { CenterMessage, ErrorState } from '@/components/ui';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { useGame } from '@/logic/game/useGame';

import { NewGame } from './new-game';
import { Playing } from './play';

const LOADING_MESSAGES = ko.shell.loading;

const ROTATION_MS = 5000;

function LoadingMessage() {
  const [idx, setIdx] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => {
      setIdx((i) => (i + 1) % LOADING_MESSAGES.length);
    }, ROTATION_MS);
    return () => clearInterval(id);
  }, []);
  return (
    <Text
      className="font-sans-semibold text-panel text-fg-muted"
      style={{ letterSpacing: 1.2 }}
    >
      {LOADING_MESSAGES[idx]}
    </Text>
  );
}

export function Shell() {
  const game = useGame();

  if (game.status === 'loading') {
    return (
      <CenterMessage>
        <ActivityIndicator color={colors.accent.fg} />
        <LoadingMessage />
      </CenterMessage>
    );
  }

  if (game.status === 'error') {
    return (
      <ErrorState
        message={game.errorMessage ?? ko.error.unknown}
        onRetry={game.refresh}
      />
    );
  }

  if (game.status === 'no-game') {
    return <NewGame onSubmit={game.startNewGame} />;
  }

  return <Playing game={game} />;
}
