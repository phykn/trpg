jest.mock('expo/fetch', () => ({ fetch: jest.fn() }));
process.env.EXPO_PUBLIC_API_URL = 'http://t';
process.env.EXPO_PUBLIC_API_USER = 'u';
process.env.EXPO_PUBLIC_API_PASS = 'p';
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { LineReader } = require('../api') as typeof import('../api');

test('NDJSON cut anywhere gives the same events', () => {
  const body = '{"type":"stage","stage":"writing"}\n{"type":"text","text":"바람이 붑니다."}\n{"type":"done","tags":[]}\n';
  const whole = new LineReader().feed(body);
  for (let cut = 1; cut < body.length; cut += 7) {
    const r = new LineReader();
    const got = [...r.feed(body.slice(0, cut)), ...r.feed(body.slice(cut)), ...r.end()];
    expect(got).toEqual(whole);
  }
  expect(whole.map((e) => e.type)).toEqual(['stage', 'text', 'done']);
});

test('a last line without a newline still counts', () => {
  const r = new LineReader();
  expect([...r.feed('{"type":"done","tags":[]}'), ...r.end()]).toEqual([{ type: 'done', tags: [] }]);
});
