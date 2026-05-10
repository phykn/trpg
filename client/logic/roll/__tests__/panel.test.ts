import { buildDiceCells } from '../panel';

describe('buildDiceCells', () => {
  test('marks cells below the required roll as failing and the required cell as selected', () => {
    const cells = buildDiceCells(13);

    expect(cells).toHaveLength(20);
    expect(cells[0]).toMatchObject({ value: 1, band: 'fail', selected: false });
    expect(cells[11]).toMatchObject({ value: 12, band: 'fail', selected: false });
    expect(cells[12]).toMatchObject({ value: 13, band: 'success', selected: true });
    expect(cells[19]).toMatchObject({ value: 20, band: 'success', selected: false });
  });
});
