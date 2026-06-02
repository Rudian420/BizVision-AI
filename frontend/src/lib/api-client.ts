/**
 * Axios API client for the BizVision backend.
 *
 * - Base URL from validated env.
 * - Attaches the bearer access token from the auth store.
 * - On 401, attempts a single refresh then retries the original request.
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

import { API_ROUTES } from '@bizvision/contracts';

import { env } from './env';

export const apiClient = axios.create({
  baseURL: env.NEXT_PUBLIC_API_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// Token accessors are injected by the auth store to avoid a circular import.
let getAccessToken: () => string | null = () => null;
let getRefreshToken: () => string | null = () => null;
let onTokenRefreshed: (accessToken: string) => void = () => {};
let onAuthFailure: () => void = () => {};

export function configureAuthBridge(bridge: {
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
  onTokenRefreshed: (accessToken: string) => void;
  onAuthFailure: () => void;
}) {
  getAccessToken = bridge.getAccessToken;
  getRefreshToken = bridge.getRefreshToken;
  onTokenRefreshed = bridge.onTokenRefreshed;
  onAuthFailure = bridge.onAuthFailure;
}

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean };
    if (error.response?.status !== 401 || original?._retried) {
      return Promise.reject(error);
    }

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      onAuthFailure();
      return Promise.reject(error);
    }

    refreshing ??= apiClient
      .post<{ access_token: string }>(API_ROUTES.auth.refresh, { refresh_token: refreshToken })
      .then((r) => r.data.access_token)
      .catch(() => null)
      .finally(() => {
        refreshing = null;
      });

    const newToken = await refreshing;
    if (!newToken) {
      onAuthFailure();
      return Promise.reject(error);
    }

    onTokenRefreshed(newToken);
    original._retried = true;
    original.headers.Authorization = `Bearer ${newToken}`;
    return apiClient(original);
  },
);
