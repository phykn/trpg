// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act } from 'react-test-renderer';

import { ko } from '@/locale/ko';
import { getVersion, listProfiles } from '@/services';
import { NewGame } from '../NewGame';

jest.mock('@/services', () => ({
  getVersion: jest.fn(),
  listProfiles: jest.fn(),
}));

describe('NewGame', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getVersion as jest.Mock).mockResolvedValue({ sha: 'test-sha' });
  });

  test('shows a localized retry message when profiles cannot be loaded', async () => {
    (listProfiles as jest.Mock).mockRejectedValue(new TypeError('Failed to fetch'));
    let root: unknown = null;

    await act(async () => {
      root = renderer.create(<NewGame onSubmit={jest.fn()} />);
      await Promise.resolve();
    });

    const text = JSON.stringify((root as { toJSON: () => unknown }).toJSON());
    expect(text).toContain(ko.error.requestInterrupted);
    expect(text).not.toContain('Failed to fetch');
  });
});
