import { Frame } from '@/components/game/Frame';
import { Resend } from '@/components/ui/Notice';
import { useGame } from '@/logic/useGame';
import { Play } from '@/screens/Play';
import { Start } from '@/screens/Start';
import { Title } from '@/screens/Title';
import { View } from 'react-native';

export default function Index() {
  const g = useGame();
  const { view, phase } = g;
  if (phase === 'loading') return <Frame>{null}</Frame>;
  if (!view || phase === 'title') {
    return (
      <Frame>
        <Title stories={g.stories} saved={g.saved} onStart={g.start} onResume={g.resume} />
        {phase === 'stuck' ? <View className="px-4 pb-4"><Resend onResend={g.resend} /></View> : null}
      </Frame>
    );
  }
  if (view.stage === 'start') {
    return (
      <Frame title={view.story.title}>
        <Start view={view} locked={phase !== 'ready'} onStart={(act) => g.send({ do: act })} />
        {phase === 'stuck' ? <View className="px-4 pb-4"><Resend onResend={g.resend} /></View> : null}
      </Frame>
    );
  }
  return (
    <Frame title={view.story.title}>
      <Play view={view} log={g.log} phase={phase} onSend={(text) => g.send({ text })} onAct={(act) => g.send({ do: act })}
        onResend={g.resend} onRetryText={g.retryText} />
    </Frame>
  );
}
