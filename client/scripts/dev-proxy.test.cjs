const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { test } = require('node:test');
const { proxyApi } = require('./dev-proxy.cjs');

async function listen(t, handler) {
  const server = http.createServer(handler).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => server.close());
  return `http://127.0.0.1:${server.address().port}`;
}

const portOf = (url) => Number(new URL(url).port);

test('a command reaches the API whole, and a conflict comes back as the API sent it', async (t) => {
  const command = { request_id: 'r1', revision: 3, do: 'a2' };
  const api = await listen(t, async (req, res) => {
    let body = '';
    for await (const chunk of req) body += chunk;
    assert.deepEqual([req.method, req.url, req.headers.authorization, JSON.parse(body)],
      ['POST', '/games/g1/commands?x=1', 'Basic bG9jYWw6bG9jYWw=', command]);
    res.writeHead(409, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ view: { revision: 4 } }));
  });
  const web = await listen(t, proxyApi(() => assert.fail('an API path fell through to Metro'), portOf(api)));
  const response = await fetch(`${web}/api/games/g1/commands?x=1`, {
    method: 'POST', headers: { Authorization: 'Basic bG9jYWw6bG9jYWw=' }, body: JSON.stringify(command),
  });
  assert.equal(response.status, 409);
  assert.deepEqual(await response.json(), { view: { revision: 4 } });
});

test('every other path is left to Metro', async (t) => {
  const middleware = proxyApi((req, res, next) => next());
  const web = await listen(t, (req, res) => middleware(req, res, () => res.end(req.url)));
  assert.equal(await (await fetch(`${web}/assets/icon.png`)).text(), '/assets/icon.png');
});

test('a stopped API answers 502 at once', async (t) => {
  const stopped = http.createServer().listen(0, '127.0.0.1');
  await once(stopped, 'listening');
  const { port } = stopped.address();
  await new Promise((resolve) => stopped.close(resolve));
  const web = await listen(t, proxyApi(() => {}, port));
  const response = await fetch(`${web}/api/stories`);
  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), { error: 'api_unavailable' });
});

test('an answer cut off midway does not take Metro down', async (t) => {
  const api = await listen(t, (req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.write('{');
    setImmediate(() => res.destroy());
  });
  const web = await listen(t, proxyApi((req, res) => res.end('web alive'), portOf(api)));
  await assert.rejects(async () => (await fetch(`${web}/api/stories`)).text());
  assert.equal(await (await fetch(`${web}/`)).text(), 'web alive');
});
