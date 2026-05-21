import * as fs from 'fs';
import * as path from 'path';

describe('Playing overlay layering', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'Playing.tsx'), 'utf8');

  test('keeps the bottom composer above panel dismissal overlays', () => {
    expect(source).toContain('activeId !== null || nearbyOpen ? 10 : 0');
  });

  test('keeps bottom controls as an overlay instead of keyboard-avoiding the log', () => {
    expect(source).not.toContain('KeyboardAvoidingView');
    expect(source).toContain("position: 'absolute'");
    expect(source).toContain('bottomInset={bottomOverlayHeight}');
    expect(source).toContain('setBottomOverlayHeight(ev.nativeEvent.layout.height)');
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

  test('builds nearby actions from the current server snapshot', () => {
    expect(source).toContain('buildNearbyPanel(storyGraph)');
  });

  test('hides stale nearby and suggestion actions after scenario completion', () => {
    expect(source).toContain('const visibleNearby = game.scenarioCompleted ? null : nearby;');
    expect(source).toContain('const visibleSuggestions = game.scenarioCompleted ? [] : suggestions;');
    expect(source).toContain('suggestions={visibleSuggestions}');
    expect(source).toContain('nearby={visibleNearby}');
  });

  test('keeps context panels and nearby panel mutually exclusive', () => {
    expect(source).toContain('const setNearbyOpenFromComposer = (open: boolean) => {');
    expect(source).toContain('if (open) setActiveId(null);');
    expect(source).toContain('onNearbyOpenChange={setNearbyOpenFromComposer}');
    expect(source).toContain('setNearbyOpen(false);');
  });

  test('only uses cues from the last log entry when it is GM narration', () => {
    expect(source).toContain('const lastLogEntry = log[log.length - 1];');
    expect(source).toContain("const latestCues = lastLogEntry?.kind === 'gm' ? lastLogEntry.cues ?? [] : [];");
    expect(source).toContain('latestCues,');
    expect(source).not.toContain('for (let i = log.length - 1; i >= 0; i -= 1)');
  });
});
