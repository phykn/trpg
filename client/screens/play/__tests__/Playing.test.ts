import * as fs from 'fs';
import * as path from 'path';

describe('Playing overlay layering', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'Playing.tsx'), 'utf8');
  const keyboardSource = fs.readFileSync(
    path.resolve(__dirname, '..', 'useKeyboardOverlay.ts'),
    'utf8',
  );

  test('keeps the bottom composer above panel dismissal overlays', () => {
    expect(source).toContain('activeId !== null || nearbyOpen ? 10 : 0');
  });

  test('keeps bottom controls as an overlay instead of keyboard-avoiding the log', () => {
    expect(source).not.toContain('KeyboardAvoidingView');
    expect(source).toContain("position: 'absolute'");
    expect(source).toContain('bottomInset={bottomOverlayHeight}');
    expect(source).toContain('setBottomOverlayHeight(ev.nativeEvent.layout.height)');
  });

  test('moves only the bottom controls when the keyboard opens', () => {
    expect(source).toContain('useKeyboardOverlay');
    expect(keyboardSource).toContain('Platform.OS === \'web\'');
    expect(keyboardSource).toContain('updateWebKeyboardOverlayHeight');
    expect(keyboardSource).toContain('window.visualViewport');
    expect(keyboardSource).toContain('webNavigator.virtualKeyboard?.boundingRect.height');
    expect(keyboardSource).toContain('isEditableElementFocused');
    expect(keyboardSource).toContain('const [keyboardOverlayHeight, setKeyboardOverlayHeight] = React.useState(0);');
    expect(keyboardSource).toContain('setKeyboardOverlayHeight(ev.endCoordinates.height)');
    expect(keyboardSource).toContain('setKeyboardOverlayHeight(0)');
    expect(source).toContain('bottom: keyboardOverlayHeight');
    expect(source).toContain('keyboardOverlayActive={keyboardOverlayHeight > 0}');
    expect(source).not.toContain('bottomInset={bottomOverlayHeight + keyboardOverlayHeight}');
  });

  test('freezes the play surface height while the keyboard overlays the screen', () => {
    expect(source).toContain('const [playSurfaceHeight, setPlaySurfaceHeight] = React.useState(0);');
    expect(source).toContain('setPlaySurfaceHeight((prev) => Math.max(prev, nextHeight));');
    expect(source).toContain('height: keyboardOverlayHeight > 0 && playSurfaceHeight > 0 ? playSurfaceHeight : undefined');
  });

  test('uses shared panel slot builder so active quests and offers stay separate', () => {
    expect(source).toContain('buildPanelSlots');
    expect(source).not.toContain('quest ?? questOffers[0] ?? null');
  });

  test('keeps free text composer available during combat', () => {
    expect(source).toContain('combat ? (');
    expect(source).toContain('<CombatStrip');
    expect(source).toContain('locked={pendingConfirmation !== null || pendingRoll !== null}');
  });

  test('locks composer actions while a pending roll is active', () => {
    expect(source).toContain('locked={pendingConfirmation !== null || pendingRoll !== null}');
    expect(source).toContain('disabled: streaming || pendingConfirmation !== null || pendingRoll !== null');
  });

  test('does not show the roll panel while pre-roll narration is streaming', () => {
    expect(source).toContain('const showRollPanel = pendingRoll !== null && !streaming;');
    expect(source).toContain(') : showRollPanel ? (');
  });

  test('disables context actions while a blocking request state is active', () => {
    expect(source).toContain('actionDisabled={streaming || pendingConfirmation !== null || pendingRoll !== null}');
  });

  test('keeps decision chips above the narration log', () => {
    expect(source.indexOf('<DecisionStateStrip items={decisionStateItems} />')).toBeLessThan(
      source.indexOf('<Log'),
    );
  });

  test('moves discoveries into the top context slots instead of always rendering above the log', () => {
    expect(source).toContain('buildPanelSlots({ hero, subject, chapter, discoveries, slotDots, scenarioCompleted: game.scenarioCompleted, quest, questOffers })');
    expect(source).not.toContain('<DiscoveriesPanel discoveries={discoveries} />');
  });

  test('marks changed top context slots until each tab is opened', () => {
    expect(source).toContain('usePanelSlotTracking');
    expect(source).toContain('const { slotDots, markSlotSeen } = usePanelSlotTracking');
    expect(source).toContain('markSlotSeen(next);');
    expect(source).not.toContain('function slotContentKeys');
    expect(source).not.toContain('setSeenSlotKeys');
  });

  test('builds nearby actions from the current server snapshot', () => {
    expect(source).toContain('buildNearbyPanel(storyGraph)');
  });

  test('hides stale nearby and suggestion actions after scenario completion', () => {
    expect(source).toContain('const visibleNearby = game.scenarioCompleted || nearby.items.length === 0 ? null : nearby;');
    expect(source).toContain('const visibleSuggestions = game.scenarioCompleted ? [] : suggestions;');
    expect(source).toContain('suggestions={visibleSuggestions}');
    expect(source).toContain('nearby={visibleNearby}');
    expect(source).toContain('quickActions={hero.canLevelUp && !game.scenarioCompleted ? [{');
    expect(source).toContain(') : game.scenarioCompleted ? null : levelUpOpen ? (');
  });

  test('hides the nearby affordance when there are no actionable nearby rows', () => {
    expect(source).toContain('const visibleNearby = game.scenarioCompleted || nearby.items.length === 0 ? null : nearby;');
  });

  test('keeps context panels and nearby panel mutually exclusive', () => {
    expect(source).toContain('const setNearbyOpenFromComposer = (open: boolean) => {');
    expect(source).toContain('if (open) setActiveId(null);');
    expect(source).toContain('if (open) setStoryDevOpen(false);');
    expect(source).toContain('onNearbyOpenChange={setNearbyOpenFromComposer}');
    expect(source).toContain('setNearbyOpen(false);');
  });

  test('closes floating panels when the keyboard opens', () => {
    expect(source).toContain(`if (typing) {
      setActiveId(null);
      setNearbyOpen(false);
      setStoryDevOpen(false);
    }`);
  });

  test('exposes generated story dev diagnostics only in dev builds', () => {
    expect(source).toContain('const showStoryDev = __DEV__ && game.gameId !== null;');
    expect(source).toContain('<StoryDevPanel gameId={game.gameId ?? \'\'} onClose={() => setStoryDevOpen(false)} />');
    expect(source).toContain('d={ICON_PATH.storyDev}');
    expect(source).toContain('text={ko.storyDev.short}');
  });

  test('only uses cues from the last log entry when it is GM narration', () => {
    expect(source).toContain('const lastLogEntry = log[log.length - 1];');
    expect(source).toContain("const latestCues = lastLogEntry?.kind === 'gm' ? lastLogEntry.cues ?? [] : [];");
    expect(source).toContain('latestCues,');
    expect(source).not.toContain('for (let i = log.length - 1; i >= 0; i -= 1)');
  });
});
