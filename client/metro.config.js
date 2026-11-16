const { getDefaultConfig } = require('expo/metro-config');
const { withNativeWind } = require('nativewind/metro');

const config = getDefaultConfig(__dirname);

// `npm run dev` serves the API under /api on the web address, so a phone needs one address for both.
if (process.env.TRPG_DEV_PROXY === '1') {
  const { proxyApi } = require('./scripts/dev-proxy.cjs');
  const enhance = config.server.enhanceMiddleware;
  config.server.enhanceMiddleware = (middleware, server) => proxyApi(enhance ? enhance(middleware, server) : middleware);
}

module.exports = withNativeWind(config, { input: './global.css' });
