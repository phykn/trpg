const { getDefaultConfig } = require('expo/metro-config');
const { withNativeWind } = require('nativewind/metro');

const config = getDefaultConfig(__dirname);
const defaultResolveRequest = config.resolver.resolveRequest;

config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (platform === 'web' && moduleName === 'react-native/Libraries/Core/InitializeCore') {
    return {
      type: 'empty',
    };
  }

  if (defaultResolveRequest) {
    return defaultResolveRequest(context, moduleName, platform);
  }

  return context.resolveRequest(context, moduleName, platform);
};

if (process.env.TRPG_DEV_PROXY === '1') {
  const { proxyApi } = require('./scripts/dev-proxy.cjs');
  const enhance = config.server.enhanceMiddleware;
  config.server.enhanceMiddleware = (middleware, server) =>
    proxyApi(enhance ? enhance(middleware, server) : middleware);
}

module.exports = withNativeWind(config, { input: './global.css' });
