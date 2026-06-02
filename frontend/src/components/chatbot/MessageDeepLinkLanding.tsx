'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { formatAuthError } from '@/lib/auth/errors';
import { useChatbotMessageDetailQuery } from '@/lib/chatbot/queries';
import { moduleById } from '@/lib/modules';

type MessageDeepLinkLandingProps = {
  messageId: string;
};

/**
 * Audit-feed deep-link landing for a chatbot message (TASK-034).
 *
 * Chatbot audit references point at one assistant message, but the
 * user-facing surface for messages is the *conversation* — the
 * workspace at `/modules/chatbot` loads the full conversation
 * thread. So this landing page:
 *   1. Resolves the message_id → conversation_id via the backend.
 *   2. Redirects to `/modules/chatbot?conversation_id={id}` so the
 *      workspace pre-loads that conversation (the workspace reads
 *      the URL param on mount — see ChatbotWorkspace).
 *
 * Render path:
 *   • loading → spinner-style placeholder
 *   • success → brief transition card + auto-redirect (router.replace
 *     happens in a useEffect tied to the resolved data)
 *   • error → render error message + back-link to the chatbot
 *     workspace as a manual fallback
 */
export function MessageDeepLinkLanding({ messageId }: MessageDeepLinkLandingProps) {
  const meta = moduleById('chatbot');
  const router = useRouter();
  const query = useChatbotMessageDetailQuery(messageId);

  const conversationId = query.data?.conversation_id;

  useEffect(() => {
    if (conversationId) {
      router.replace(`/modules/chatbot?conversation_id=${conversationId}`);
    }
  }, [conversationId, router]);

  const errorMessage = query.isError ? formatAuthError(query.error) : null;

  return (
    <div className="flex flex-col gap-6">
      <header className="border-b border-white/10 pb-6">
        <div className="mb-2 flex items-center gap-3">
          <Link
            href="/decisions"
            className="font-ui text-[10px] uppercase tracking-widest text-text-secondary underline-offset-4 hover:text-text-primary hover:underline"
          >
            ← ML Decision Feed
          </Link>
        </div>
        <div className="mb-2 flex items-center gap-3">
          <span className="font-data text-3xl" style={{ color: meta.accent }}>
            {meta.glyph}
          </span>
          <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            chatbot · message
          </span>
        </div>
        <h2 className="font-ui text-3xl font-semibold tracking-tight text-text-primary">
          {query.isLoading
            ? 'Resolving conversation…'
            : query.data?.conversation_title || 'Message not found'}
        </h2>
        {query.data && (
          <p className="mt-2 font-data text-[11px] text-text-secondary">
            position {query.data.position} · role {query.data.role} ·{' '}
            {new Date(query.data.created_at).toISOString().slice(0, 10)}
          </p>
        )}
      </header>

      {errorMessage && (
        <p
          role="alert"
          className="rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-sm text-coral"
        >
          {errorMessage}
        </p>
      )}

      {query.data && (
        <section
          aria-label="Message content preview"
          className="rounded-2xl border border-white/10 bg-white/[0.02] p-5"
        >
          <header className="mb-3 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            Message preview
          </header>
          <p className="font-ui text-sm leading-relaxed text-text-primary">
            {query.data.content.length > 600
              ? `${query.data.content.slice(0, 600)}…`
              : query.data.content}
          </p>
          <p className="mt-4 font-ui text-xs text-text-secondary">
            Opening the conversation surface so you can see the full thread…
          </p>
        </section>
      )}

      {/* Manual fallback link — never harmful even when the auto-redirect
          fires; useful if the redirect race or the user navigates away
          before it runs. */}
      {conversationId && (
        <Link
          href={`/modules/chatbot?conversation_id=${conversationId}`}
          className="self-start rounded-md border border-white/20 px-4 py-2 font-ui text-sm text-text-primary transition hover:border-white/40"
        >
          Open conversation →
        </Link>
      )}
    </div>
  );
}
