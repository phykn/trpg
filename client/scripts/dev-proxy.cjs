const http = require('node:http');

// Metro middleware for `npm run dev`: /api/* goes to the local API, so a phone uses one address for page and API.
function proxyApi(next, port = 8000) {
  return (req, res, done) => {
    if (!req.url.startsWith('/api/')) return next(req, res, done);
    const upstream = http.request({
      hostname: '127.0.0.1', port, path: req.url.slice('/api'.length), method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${port}` },
    }, (response) => {
      res.writeHead(response.statusCode, response.headers);
      response.on('error', () => res.destroy());
      response.pipe(res);
    });
    // A stopped API answers 502 at once instead of leaving the page waiting, and never takes Metro down.
    upstream.on('error', () => {
      if (res.headersSent) return res.destroy();
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'api_unavailable' }));
    });
    req.on('error', () => upstream.destroy());
    res.on('close', () => upstream.destroy());
    req.pipe(upstream);
  };
}

module.exports = { proxyApi };
