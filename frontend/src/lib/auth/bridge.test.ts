/**
 * Auth bridge tests — verifies that installing the bridge gives the
 * api-client read access to the store's tokens and that refresh /
 * 401 callbacks flow back into the store as `setAccessToken` and
 * `clear`.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from '@/lib/store/use-auth-store';

import { installAuthBridge } from './bridge';

// We capture whatever the bridge installs by mocking the configurator.
// The bridge is idempotent — only the FIRST install wins per module
// load; tests reset via `vi.resetModules()` to get a fresh install.

const captured: {
  getAccessToken?: () => string | null;
  getRefreshToken?: () => string | null;
  onTokenRefreshed?: (t: string) => void;
  onAuthFailure?: () => void;
} = {};

vi.mock('@/lib/api-client', () => ({
  configureAuthBridge: (bridge: {
    getAccessToken: () => string | null;
    getRefreshToken: () => string | null;
    onTokenRefreshed: (t: string) => void;
    onAuthFailure: () => void;
  }) => {
    captured.getAccessToken = bridge.getAccessToken;
    captured.getRefreshToken = bridge.getRefreshToken;
    captured.onTokenRefreshed = bridge.onTokenRefreshed;
    captured.onAuthFailure = bridge.onAuthFailure;
  },
}));

beforeEach(() => {
  useAuthStore.setState({
    accessToken: null,
    refreshToken: null,
    user: null,
    hydrated: false,
    isAuthenticated: false,
  });
  window.localStorage.clear();
  installAuthBridge();
});

afterEach(() => {
  // Reset module state so each test starts with a fresh `installed=false`.
  vi.resetModules();
});

describe('installAuthBridge', () => {
  it('exposes the store getters to the api-client', () => {
    useAuthStore.setState({
      accessToken: 'tok-1',
      refreshToken: 'ref-1',
      isAuthenticated: true,
    });
    expect(captured.getAccessToken?.()).toBe('tok-1');
    expect(captured.getRefreshToken?.()).toBe('ref-1');
  });

  it('onTokenRefreshed updates the store', () => {
    useAuthStore.setState({
      accessToken: 'tok-old',
      refreshToken: 'ref-1',
      isAuthenticated: true,
    });
    captured.onTokenRefreshed?.('tok-new');
    expect(useAuthStore.getState().accessToken).toBe('tok-new');
    expect(useAuthStore.getState().refreshToken).toBe('ref-1');
  });

  it('onAuthFailure clears the store', () => {
    useAuthStore.setState({
      accessToken: 'tok-1',
      refreshToken: 'ref-1',
      isAuthenticated: true,
    });
    captured.onAuthFailure?.();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
  });
});
