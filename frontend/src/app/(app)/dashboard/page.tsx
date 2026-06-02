'use client';

import { ModuleCard } from '@/components/shell/ModuleCard';
import { useAuth } from '@/hooks/use-auth';
import { MODULES } from '@/lib/modules';

export default function DashboardPage() {
  const { user } = useAuth();
  const greeting = (() => {
    const name = user?.full_name?.split(/\s+/)[0] ?? user?.email?.split('@')[0];
    return name ? `Welcome back, ${name}.` : 'Welcome back.';
  })();

  return (
    <div>
      <header className="mb-10">
        <h2 className="font-ui text-3xl font-semibold tracking-tight text-text-primary">{greeting}</h2>
        <p className="mt-2 font-ui text-sm text-text-secondary">
          Your AI modules are warm and ready. Open one to start an analysis.
        </p>
      </header>

      <section aria-label="Modules" className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {MODULES.map((m) => (
          <ModuleCard key={m.id} module={m} />
        ))}
      </section>
    </div>
  );
}
