'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { MODULES } from '@/lib/modules';
import { cn } from '@/lib/utils';

/**
 * Vertical module navigator for the post-login command center.
 *
 * Each module gets its accent colour for the active state — same
 * palette as the cinematic landing's planet system, so the visual
 * thread carries across.
 */
const TOP_LINKS = [
  { href: '/dashboard', label: 'Overview', glyph: '✶' },
  { href: '/decisions', label: 'ML Decision Feed', glyph: '◬' },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden border-r border-white/10 bg-white/[0.02] md:flex md:w-64 md:flex-col">
      <div className="flex h-16 items-center px-6 font-ui text-base font-semibold tracking-tight text-text-primary">
        <span className="mr-2 font-data text-cyan">◈</span>
        BizVision AI
      </div>

      <nav className="flex-1 space-y-1 px-3 pt-2" aria-label="Workspace navigation">
        {TOP_LINKS.map((link) => (
          <SidebarLink
            key={link.href}
            href={link.href}
            active={
              link.href === '/dashboard'
                ? pathname === link.href
                : pathname.startsWith(link.href)
            }
            glyph={link.glyph}
            accent="#FFFFFF"
          >
            {link.label}
          </SidebarLink>
        ))}

        <div className="mt-6 px-3 font-ui text-[10px] uppercase tracking-widest text-text-secondary">Modules</div>

        {MODULES.map((m) => {
          const href = `/modules/${m.id}`;
          return (
            <SidebarLink
              key={m.id}
              href={href}
              active={pathname.startsWith(href)}
              glyph={m.glyph}
              accent={m.accent}
            >
              {m.label}
            </SidebarLink>
          );
        })}
      </nav>

      <div className="px-6 py-4 font-data text-[10px] uppercase tracking-widest text-text-secondary">
        v1.0 · cinematic-os
      </div>
    </aside>
  );
}

type SidebarLinkProps = {
  href: string;
  active: boolean;
  glyph: string;
  accent: string;
  children: React.ReactNode;
};

function SidebarLink({ href, active, glyph, accent, children }: SidebarLinkProps) {
  return (
    <Link
      href={href}
      className={cn(
        'flex items-center gap-3 rounded-md px-3 py-2 font-ui text-sm text-text-secondary transition hover:text-text-primary',
        active && 'bg-white/[0.05] text-text-primary',
      )}
      style={active ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}
    >
      <span className="font-data text-base" style={{ color: active ? accent : undefined }}>
        {glyph}
      </span>
      <span>{children}</span>
    </Link>
  );
}
