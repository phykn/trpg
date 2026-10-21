// Explicit local settings; keep startup independent of personal env files.
const localEnv = (url) => ({
  ...process.env,
  EXPO_NO_DOTENV: '1',
  EXPO_PUBLIC_API_URL: url,
  EXPO_PUBLIC_API_USER: 'local',
  EXPO_PUBLIC_API_PASS: 'local',
});

// 'engine' for this game's API, 'refused' when nothing listens, 'other' for anything else.
async function health(base, ms) {
  try {
    const response = await fetch(`${base}/health`, { signal: AbortSignal.timeout(ms) });
    return response.ok && (await response.json()).mode === 'engine' ? 'engine' : 'other';
  } catch (error) {
    return error.cause?.code === 'ECONNREFUSED' ? 'refused' : 'other';
  }
}

module.exports = { localEnv, health };
