import type { Metadata } from 'next';
import Link from 'next/link';

import { AuthShell } from '@/components/auth/AuthShell';
import { RegisterForm } from '@/components/auth/RegisterForm';

export const metadata: Metadata = {
  title: 'Create account',
};

export default function RegisterPage() {
  return (
    <AuthShell
      title="Create your account"
      subtitle="Start your BizVision intelligence workspace in 60 seconds."
      footer={
        <>
          Already have an account?{' '}
          <Link href="/login" className="text-cyan hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <RegisterForm />
    </AuthShell>
  );
}
