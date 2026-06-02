'use client';

import { useState, type FormEvent, type KeyboardEvent } from 'react';

import { CONTEXT_MODULES } from '@/lib/chatbot/format';
import type { ChatMessageRequest } from '@/lib/chatbot/types';
import { cn } from '@/lib/utils';

type ChatComposerProps = {
  conversationId: string | null;
  onSubmit: (request: ChatMessageRequest) => void;
  /** True while the send-message mutation is in flight. */
  submitting: boolean;
};

const MAX_CONTENT = 4000;

/**
 * Sticky composer at the bottom of the chat workspace.
 *
 * Behaviour:
 *   • Cmd/Ctrl + Enter sends the message; plain Enter inserts a
 *     newline so the user can compose multi-line questions without
 *     accidentally firing the send.
 *   • Module-context chips fold the named module's persisted data
 *     into the assistant's retrieval pass via `include_modules`.
 *     Selection state is local — every new conversation starts with
 *     an empty selection so the assistant defaults to all-module
 *     scope, matching the backend's wave-1 behaviour.
 *   • Content length is shown live; the send button disables when
 *     the textarea is empty or over the 4000-char API cap.
 */
export function ChatComposer({ conversationId, onSubmit, submitting }: ChatComposerProps) {
  const [content, setContent] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const trimmed = content.trim();
  const overCap = trimmed.length > MAX_CONTENT;
  const canSend = !submitting && trimmed.length > 0 && !overCap;

  function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!canSend) return;
    const request: ChatMessageRequest = {
      content: trimmed,
      include_modules: Array.from(selected),
      conversation_id: conversationId ?? null,
    };
    onSubmit(request);
    setContent('');
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      handleSubmit();
    }
  }

  function toggleModule(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-white/10 bg-white/[0.03] p-3"
    >
      <fieldset className="mb-2">
        <legend className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          Module context (optional)
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {CONTEXT_MODULES.map((meta) => {
            const active = selected.has(meta.id);
            return (
              <button
                key={meta.id}
                type="button"
                onClick={() => toggleModule(meta.id)}
                aria-pressed={active}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-ui text-[11px] uppercase tracking-widest transition',
                )}
                style={{
                  color: active ? meta.accent : 'rgba(255,255,255,0.55)',
                  borderColor: active ? `${meta.accent}88` : 'rgba(255,255,255,0.12)',
                  backgroundColor: active ? `${meta.accent}1A` : 'transparent',
                }}
              >
                <span aria-hidden className="font-data">
                  {meta.glyph}
                </span>
                {meta.id}
              </button>
            );
          })}
        </div>
      </fieldset>

      <textarea
        name="content"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={3}
        placeholder="Ask the AI advisor anything — Cmd/Ctrl + Enter sends."
        className="w-full resize-none rounded-lg border border-white/10 bg-void/40 px-3 py-2 font-ui text-sm text-text-primary outline-none transition focus:border-coral focus:ring-1 focus:ring-coral/40"
      />

      <div className="mt-2 flex items-center justify-between gap-3">
        <span
          className={cn(
            'font-data text-[10px] uppercase tracking-widest',
            overCap ? 'text-coral' : 'text-text-secondary',
          )}
        >
          {trimmed.length} / {MAX_CONTENT}
          {selected.size > 0 && (
            <span className="ml-3 normal-case text-text-secondary">
              · {selected.size} module{selected.size === 1 ? '' : 's'} folded in
            </span>
          )}
        </span>

        <button
          type="submit"
          disabled={!canSend}
          className="rounded-lg bg-coral px-4 py-1.5 font-ui text-sm font-medium text-void transition hover:bg-coral/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? 'Sending…' : 'Send'}
        </button>
      </div>
    </form>
  );
}
