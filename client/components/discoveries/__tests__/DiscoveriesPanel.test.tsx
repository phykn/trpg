// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act } from 'react-test-renderer';

import { DiscoveriesPanel } from '../DiscoveriesPanel';

test('renders memories and clues', async () => {
  let root: unknown = null;
  await act(async () => {
    root = renderer.create(
      <DiscoveriesPanel
        discoveries={{
          memories: [
            {
              id: 'mem_tore_ticket_001',
              title: '당신은 표를 찢었습니다.',
              summary: '당신은 표를 찢었습니다.',
              stability: 'campaign',
              turnId: 3,
            },
          ],
          clues: [
            {
              id: 'clue_wet_ticket_001',
              title: '젖은 승선표',
              summary: '표가 젖어 있습니다.',
              stability: 'scene',
              turnId: 4,
            },
          ],
        }}
      />,
    );
  });

  const tree = (root as { toJSON: () => unknown }).toJSON();
  expect(JSON.stringify(tree)).toContain('젖은 승선표');
  expect(JSON.stringify(tree)).toContain('당신은 표를 찢었습니다.');
});

test('does not repeat a discovery summary when it matches the title', async () => {
  let root: unknown = null;
  await act(async () => {
    root = renderer.create(
      <DiscoveriesPanel
        discoveries={{
          memories: [
            {
              id: 'mem_ellie_approach',
              title: '엘리에게 친근하게 말을 건네기 위해 접근했습니다.',
              summary: '엘리에게 친근하게 말을 건네기 위해 접근했습니다.',
              stability: 'campaign',
              turnId: 9,
            },
          ],
          clues: [],
        }}
      />,
    );
  });

  const tree = (root as { toJSON: () => unknown }).toJSON();
  const text = JSON.stringify(tree);
  const matches = text.match(/엘리에게 친근하게 말을 건네기 위해 접근했습니다\./g) ?? [];
  expect(matches).toHaveLength(1);
});
