import { ActivityIndicator, Text } from 'react-native';

import { CenterMessage, ErrorState } from '@/components/ui';
import { colors } from '@/design/tokens';
import { useGame } from '@/hooks/useGame';

import { NewGame } from './new-game';
import { Playing } from './Playing';

export function Shell() {
  const game = useGame();

  if (game.status === 'loading') {
    return (
      <CenterMessage>
        <ActivityIndicator color={colors.accent.fg} />
        <Text
          className="font-sans-semibold text-meta text-fg-subtle"
          style={{ letterSpacing: 1.2 }}
        >
          불러오는 중
        </Text>
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
