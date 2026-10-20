const unavailable = () => Response.json({ error: 'api_unavailable' }, { status: 502 });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/api/')) return env.ASSETS.fetch(request);
    const origin = await env.TUNNEL.get('origin');
    if (!origin) return unavailable();
    try {
      const response = await fetch(new Request(new URL(url.pathname.slice(4) + url.search, origin), request));
      // A quick tunnel whose Mac side is gone answers with Cloudflare's own 530 page.
      return response.status === 530 ? unavailable() : response;
    } catch {
      return unavailable();
    }
  },
};
