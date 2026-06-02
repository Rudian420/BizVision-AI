/**
 * Auth client — thin wrappers around the `/auth/*` REST endpoints.
 *
 * Returns parsed response bodies. Errors propagate as axios errors
 * (the api-client interceptor handles 401 → refresh transparently);
 * the auth pages catch them locally and surface the backend's
 * `detail` field as the form error.
 */

import { API_ROUTES } from '@bizvision/contracts';

import { apiClient } from '@/lib/api-client';

import type {
  UserLoginRequest,
  UserLoginResponse,
  UserProfile,
  UserRegisterRequest,
} from './types';

export async function registerUser(body: UserRegisterRequest): Promise<UserLoginResponse> {
  const res = await apiClient.post<UserLoginResponse>(API_ROUTES.auth.register, body);
  return res.data;
}

export async function loginUser(body: UserLoginRequest): Promise<UserLoginResponse> {
  const res = await apiClient.post<UserLoginResponse>(API_ROUTES.auth.login, body);
  return res.data;
}

export async function logoutUser(refreshToken: string): Promise<void> {
  await apiClient.post(API_ROUTES.auth.logout, { refresh_token: refreshToken });
}

export async function fetchCurrentUser(): Promise<UserProfile> {
  const res = await apiClient.get<UserProfile>(API_ROUTES.auth.me);
  return res.data;
}
