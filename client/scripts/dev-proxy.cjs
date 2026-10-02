const http = require('node:http');

function proxyApi(next, port = 8000) {
  return (req, res, done) => {
    if (!req.url.startsWith('/api/')) return next(req, res, done);
    const upstream = http.request({
      hostname: '127.0.0.1', port, path: req.url.slice(4), method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${port}` },
    }, (response) => {
      res.writeHead(response.statusCode, response.headers);
      response.on('error', () => res.destroy());
      response.pipe(res);
    });
    upstream.on('error', () => {
      if (res.headersSent) return res.destroy();
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'api_unavailable' }));
    });
    req.on('aborted', () => upstream.destroy());
    req.on('error', () => upstream.destroy());
    res.on('close', () => upstream.destroy());
    req.pipe(upstream);
  };
}

module.exports = { proxyApi };
