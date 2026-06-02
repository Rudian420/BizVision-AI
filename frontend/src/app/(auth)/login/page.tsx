import type { Metadata } from 'next';
import Link from 'next/link';

import { AuthShell } from '@/components/auth/AuthShell';
import { LoginForm } from '@/components/auth/LoginForm';

export const metadata: Metadata = {
  title: 'Sign in',
};

export default function LoginPage() {
  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your BizVision command center."
      footer={
        <>
          Don&rsquo;t have an account?{' '}
          <Link href="/register" className="text-cyan hover:underline">
            Create one
          </Link>
        </>
      }
    >
      <LoginForm />
    </AuthShell>
  );
}
