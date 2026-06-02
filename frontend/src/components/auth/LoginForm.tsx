'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { formatAuthError } from '@/lib/auth/errors';
import { useAuth } from '@/hooks/use-auth';

import { FormField } from './FormField';

export function LoginForm() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login({ email, password });
      router.replace('/dashboard');
    } catch (err) {
      setError(formatAuthError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <FormField
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <FormField
        label="Password"
        type="password"
        name="password"
        autoComplete="current-password"
        required
        minLength={8}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      {error && (
        <p role="alert" className="mb-4 rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-xs text-coral">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-cyan px-4 py-2 font-ui text-sm font-medium text-void shadow-glow-cyan transition hover:bg-cyan/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  );
}
