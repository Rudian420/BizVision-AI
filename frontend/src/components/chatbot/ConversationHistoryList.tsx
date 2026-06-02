'use client';

import {
  formatRelativeTime,
  freshnessTier,
  moduleMetaById,
  previewSnippet,
} from '@/lib/chatbot/format';
import type { ConversationSummary } from '@/lib/chatbot/types';
import { cn } from '@/lib/utils';

type ConversationHistoryListProps = {
  conversations: ConversationSummary[];
  activeId: string | null;
  onSelect: (conversationId: string) => void;
  onNew: () => void;
  isLoading?: boolean;
  isError?: boolean;
};

/**
 * Right-rail list of the caller's past conversations.
 *
 * Each card shows the title (which the backend seeds from the first
 * user message in TASK-014), the modules-in-scope as accent chips,
 * a relative-time stamp + freshness pip (cyan / gold / dim), and
 * the conversation's total message count. The whole row is a
 * `<button>` so keyboard navigation works without extra handlers.
 */
export function ConversationHistoryList({
  conversations,
  activeId,
  onSelect,
  onNew,
  isLoading,
  isError,
}: ConversationHistoryListProps) {
  return (
    <aside
      aria-label="Conversation history"
      className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.02] p-3"
    >
      <header className="mb-3 flex items-center justify-between">
        <h3 className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          History
        </h3>
        <button
          type="button"
          onClick={onNew}
          className="rounded-md border border-white/10 px-2 py-1 font-ui text-[11px] uppercase tracking-widest text-text-secondary transition hover:border-coral/40 hover:text-coral"
        >
          + new
        </button>
      </header>

      {isError && (
        <p className="rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-xs text-coral">
          Couldn&rsquo;t load past conversations.
        </p>
      )}

      {isLoading && !isError && (
        <p className="font-ui text-xs text-text-secondary">Loading…</p>
      )}

      {!isLoading && !isError && conversations.length === 0 && (
        <p className="font-ui text-xs text-text-secondary">
          No past conversations yet — your first chat will appear here.
        </p>
      )}

      <ul className="flex-1 space-y-2 overflow-y-auto pr-1">
        {conversations.map((c) => {
          const tier = freshnessTier(c.updated_at);
          const active = c.conversation_id === activeId;
          return (
            <li key={c.conversation_id}>
              <button
                type="button"
                onClick={() => onSelect(c.conversation_id)}
                aria-current={active ? 'true' : undefined}
                className={cn(
                  'w-full rounded-lg border px-3 py-2 text-left transition',
                  active
                    ? 'border-coral/40 bg-coral/[0.06]'
                    : 'border-white/10 bg-transparent hover:border-white/20',
                )}
              >
                <div className="flex items-center justify-between gap-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
                  <FreshnessPip tier={tier} />
                  <span>{formatRelativeTime(c.updated_at)}</span>
                </div>
                <div className="mt-1 font-ui text-sm text-text-primary">
                  {previewSnippet(c.title, 60)}
                </div>
                <div className="mt-1 flex items-center justify-between gap-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
                  <span>
                    {c.message_count} message{c.message_count === 1 ? '' : 's'}
                  </span>
                  <ModuleChips ids={c.modules_in_scope} />
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

function FreshnessPip({ tier }: { tier: ReturnType<typeof freshnessTier> }) {
  const colour =
    tier === 'fresh' ? 'bg-cyan' : tier === 'recent' ? 'bg-gold' : 'bg-text-secondary/50';
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden className={cn('h-1.5 w-1.5 rounded-full', colour)} />
      {tier}
    </span>
  );
}

function ModuleChips({ ids }: { ids: string[] }) {
  if (!ids || ids.length === 0) return <span aria-hidden />;
  return (
    <span className="flex gap-1">
      {ids.slice(0, 4).map((id) => {
        const meta = moduleMetaById(id);
        const colour = meta?.accent ?? '#7C3AED';
        return (
          <span
            key={id}
            title={id}
            aria-label={id}
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: colour }}
          />
        );
      })}
    </span>
  );
}
