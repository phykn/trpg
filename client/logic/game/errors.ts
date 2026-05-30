import { ko } from '@/locale/ko';

export function errorMessageForDisplay(err: unknown): string {
  const message = err instanceof Error ? err.message : String(err);
  if (
    message === 'network error'
    || message.includes('stream ended without final payload')
    || message.toLowerCase().includes('failed to fetch')
  ) {
    return ko.error.requestInterrupted;
  }
  return message;
}
