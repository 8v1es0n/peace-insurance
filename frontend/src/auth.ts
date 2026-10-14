import type { AuthSession } from './types';

const STORAGE_KEY = 'insurance-mall-auth-v2';

export const DEFAULT_SESSION: AuthSession = {
  user: {
    id: 1,
    username: 'heima',
    email: 'heima@example.com',
    displayName: '黑马-虎哥',
  },
};

export function readSession(): AuthSession | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value ? (JSON.parse(value) as AuthSession) : null;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
