'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { formatAuthError } from '@/lib/auth/errors';
import { useAuth } from '@/hooks/use-auth';

import { FormField } from './FormField';

export function RegisterForm() {
  const router = useRouter();
  const { register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await register({
        email,
        password,
        full_name: fullName || undefined,
        company_name: companyName || undefined,
      });
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
        label="Password (min 8 chars)"
        type="password"
        name="password"
        autoComplete="new-password"
        required
        minLength={8}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <FormField
        label="Full name (optional)"
        type="text"
        name="full_name"
        autoComplete="name"
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
      />
      <FormField
        label="Company name (optional)"
        type="text"
        name="company_name"
        autoComplete="organization"
        value={companyName}
        onChange={(e) => setCompanyName(e.target.value)}
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
        {submitting ? 'Creating account…' : 'Create account'}
      </button>
    </form>
  );
}
