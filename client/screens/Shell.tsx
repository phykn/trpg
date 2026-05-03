import React from 'react';
import { ActivityIndicator, Text } from 'react-native';

import { CenterMessage, ErrorState } from '@/components/ui';
import { colors } from '@/design/tokens';
import { useGame } from '@/hooks/useGame';

import { NewGame } from './new-game';
import { Playing } from './play';

const LOADING_MESSAGES = [
  '세계 펼치는 중',
  '모닥불 지피는 중',
  '지도에 잉크 묻히는 중',
  '별빛 살피는 중',
  '이야기의 첫 줄 적는 중',
];

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
        message={game.errorMessage ?? '알 수 없는 오류'}
        onRetry={game.refresh}
      />
    );
  }

  if (game.status === 'no-game') {
    return <NewGame onSubmit={game.startNewGame} />;
  }

  return <Playing game={game} />;
}
