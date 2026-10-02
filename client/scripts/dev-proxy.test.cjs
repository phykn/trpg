const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { test } = require('node:test');
const { proxyApi } = require('./dev-proxy.cjs');

async function listen(t, handler) {
  const server = http.createServer(handler).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => server.close());
  return server;
}

test('forwards an authenticated choice, query and receipt and preserves conflict responses', async (t) => {
  const api = await listen(t, async (req, res) => {
    assert.equal(req.url, '/adventure/adv_saved/choose?source=phone');
    assert.equal(req.method, 'POST');
    assert.equal(req.headers.authorization, 'Basic bG9jYWw6bG9jYWw=');
    let body = '';
    for await (const chunk of req) body += chunk;
    assert.deepEqual(JSON.parse(body), { option_id: 'move:quay', revision: 3, request_id: 'same-receipt' });
    res.writeHead(409, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ detail: 'stale choice' }));
  });
  const web = await listen(t, proxyApi(() => assert.fail('API request fell through'), api.address().port));
  const response = await fetch(`http://127.0.0.1:${web.address().port}/api/adventure/adv_saved/choose?source=phone`, {
    method: 'POST', headers: { Authorization: 'Basic bG9jYWw6bG9jYWw=', 'Content-Type': 'application/json' },
    body: JSON.stringify({ option_id: 'move:quay', revision: 3, request_id: 'same-receipt' }),
  });
  assert.equal(response.status, 409);
  assert.deepEqual(await response.json(), { detail: 'stale choice' });
});

test('leaves web routes to Metro', async (t) => {
  const middleware = proxyApi((req, res, next) => next());
  const web = await listen(t, (req, res) => middleware(req, res, () => res.end(req.url)));
  const response = await fetch(`http://127.0.0.1:${web.address().port}/assets/example.png`);
  assert.equal(await response.text(), '/assets/example.png');
});

test('returns 502 instead of hanging when the API is stopped', async (t) => {
  const api = await listen(t, () => {});
  const port = api.address().port;
  await new Promise((resolve) => api.close(resolve));
  const web = await listen(t, proxyApi(() => {}, port));
  const response = await fetch(`http://127.0.0.1:${web.address().port}/api/adventure/catalog`);
  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), { error: 'api_unavailable' });
});

test('a broken API response does not take down the web server', async (t) => {
  const api = await listen(t, (req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.write('{');
    setImmediate(() => res.destroy());
  });
  const web = await listen(t, proxyApi((req, res) => res.end('web alive'), api.address().port));
  const url = `http://127.0.0.1:${web.address().port}`;
  await assert.rejects(async () => {
    const response = await fetch(`${url}/api/adventure/catalog`);
    await response.text();
  });
  assert.equal(await (await fetch(`${url}/`)).text(), 'web alive');
});
