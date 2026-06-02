/**
 * `formatAuthError` unit tests — covers the shapes the backend can
 * actually return: string `detail`, Pydantic ValidationError array,
 * 401 / 409 / network errors, and the unknown-error fallback.
 */

import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import { formatAuthError } from './errors';

function makeAxiosError(opts: {
  status?: number;
  data?: unknown;
  message?: string;
  code?: string;
}): AxiosError {
  const headers = new AxiosHeaders();
  const err = new AxiosError(
    opts.message ?? 'Request failed',
    opts.code,
    { headers, url: '/x', method: 'post' } as never,
    null,
    opts.status === undefined
      ? undefined
      : {
          status: opts.status,
          statusText: '',
          data: opts.data,
          headers,
          config: { headers, url: '/x' } as never,
        },
  );
  return err;
}

describe('formatAuthError', () => {
  it('surfaces a string `detail` from the backend', () => {
    const err = makeAxiosError({ status: 400, data: { detail: 'Email already taken.' } });
    expect(formatAuthError(err)).toBe('Email already taken.');
  });

  it('joins Pydantic ValidationError messages', () => {
    const err = makeAxiosError({
      status: 422,
      data: {
        detail: [
          { loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'value_error.email' },
          { loc: ['body', 'password'], msg: 'ensure this value has at least 8 characters', type: 'value_error.any_str.min_length' },
        ],
      },
    });
    expect(formatAuthError(err)).toBe(
      'value is not a valid email address; ensure this value has at least 8 characters',
    );
  });

  it('falls back to "Invalid email or password" on a 401 without detail', () => {
    const err = makeAxiosError({ status: 401, data: {} });
    expect(formatAuthError(err)).toBe('Invalid email or password.');
  });

  it('falls back to "That account already exists" on a 409 without detail', () => {
    const err = makeAxiosError({ status: 409, data: {} });
    expect(formatAuthError(err)).toBe('That account already exists.');
  });

  it('handles network errors', () => {
    const err = makeAxiosError({ code: 'ERR_NETWORK', message: 'Network Error' });
    expect(formatAuthError(err)).toBe("Couldn't reach the backend — check it's running.");
  });

  it('passes through a non-axios Error message', () => {
    expect(formatAuthError(new Error('Boom'))).toBe('Boom');
  });

  it('returns a generic fallback for unknown shapes', () => {
    expect(formatAuthError(42)).toBe('Something went wrong. Please try again.');
  });
});
