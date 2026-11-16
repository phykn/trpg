import { View } from 'react-native';

import { Frame } from '@/components/game/Frame';
import { Resend } from '@/components/ui/Resend';
import { useGame } from '@/logic/useGame';
import { Ending } from '@/screens/Ending';
import { Play } from '@/screens/Play';
import { Start } from '@/screens/Start';
import { Title } from '@/screens/Title';

// The game state picks the screen (docs/game/07-screen.md 1).
export default function Index() {
  const g = useGame();
  const { view, phase } = g;
  if (phase === 'loading') return <Frame>{null}</Frame>;
  const resend = phase === 'stuck' ? <View className="px-4 pb-4"><Resend onResend={g.resend} /></View> : null;
  if (!view || phase === 'title') {
    return (
      <Frame>
        <Title stories={g.stories} saved={g.saved} onStart={g.start} onResume={g.resume} />
        {resend}
      </Frame>
    );
  }
  if (view.stage === 'start') {
    return (
      <Frame title={view.story.title}>
        <Start view={view} locked={phase !== 'ready'} onStart={(act) => g.send({ do: act })} />
        {resend}
      </Frame>
    );
  }
  return (
    <Frame title={view.story.title}>
      {view.stage === 'over' ? <Ending view={view} log={g.log} phase={phase} onRetryText={g.retryText} onLeave={g.leave} /> : (
        <Play view={view} log={g.log} outgoing={g.outgoing} phase={phase} send={g.send} onResend={g.resend}
          onRetryText={g.retryText} onHome={g.home} />
      )}
    </Frame>
  );
}
