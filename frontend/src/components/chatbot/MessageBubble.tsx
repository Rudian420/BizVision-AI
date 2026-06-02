'use client';

import { memo } from 'react';

import { formatClockTime } from '@/lib/chatbot/format';
import type { ChatRole, SourceReference } from '@/lib/chatbot/types';
import { cn } from '@/lib/utils';

import { SourcesList } from './SourcesList';

type MessageBubbleProps = {
  role: ChatRole;
  content: string;
  createdAt?: string;
  reasoningTrace?: string[];
  sources?: SourceReference[];
};

/**
 * One message in the conversation thread.
 *
 * Visual posture:
 *   • user → right-aligned, cyan accent rail (the colour of
 *     "thinking input")
 *   • assistant → left-aligned, coral accent rail (the chatbot
 *     module's own accent — same as the cinematic landing's planet)
 *   • system → centred dim notice (no rail, no bubble chrome)
 *
 * Assistant bubbles can collapse a reasoning trace (one-line
 * summary by default; tap to expand) so the thread stays scannable.
 * Sources render below the content via the shared `SourcesList`.
 *
 * **Perf (TASK-039)**: wrapped in `React.memo` so the WS streaming path
 * doesn't re-render already-persisted turns every time a new token
 * lands on the in-flight bubble. The persisted turns are
 * structurally stable; their `key`s are content-derived; reference
 * equality is the right cheap check.
 */
export const MessageBubble = memo(function MessageBubble({
  role,
  content,
  createdAt,
  reasoningTrace,
  sources,
}: MessageBubbleProps) {
  if (role === 'system') {
    return (
      <li className="my-2 flex justify-center font-ui text-[11px] uppercase tracking-widest text-text-secondary">
        {content}
      </li>
    );
  }

  const isUser = role === 'user';
  const railColour = isUser ? '#00F5FF' : '#FF3B6B';
  const wrapperAlign = isUser ? 'justify-end' : 'justify-start';

  return (
    <li className={cn('my-3 flex', wrapperAlign)}>
      <article
        className={cn(
          'max-w-[80%] rounded-2xl border border-white/10 bg-white/[0.02] px-4 py-3',
          isUser ? 'rounded-br-sm' : 'rounded-bl-sm',
        )}
        style={{
          boxShadow: isUser ? `inset -3px 0 0 ${railColour}` : `inset 3px 0 0 ${railColour}`,
        }}
      >
        <header className="mb-1 flex items-baseline justify-between gap-3 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          <span>{isUser ? 'You' : 'Assistant'}</span>
          {createdAt && <span className="font-data normal-case">{formatClockTime(createdAt)}</span>}
        </header>

        <p className="font-ui text-sm leading-relaxed text-text-primary">{content}</p>

        {!isUser && reasoningTrace && reasoningTrace.length > 0 && (
          <ReasoningCollapse trace={reasoningTrace} />
        )}

        {!isUser && sources && sources.length > 0 && <SourcesList sources={sources} />}
      </article>
    </li>
  );
});

function ReasoningCollapse({ trace }: { trace: string[] }) {
  return (
    <details className="mt-3 font-ui text-xs">
      <summary className="cursor-pointer text-text-secondary hover:text-text-primary">
        {trace.length} reasoning step{trace.length === 1 ? '' : 's'}
      </summary>
      <ol className="mt-2 list-decimal space-y-1 pl-5 text-text-secondary">
        {trace.map((step, i) => (
          <li key={`${i}-${step.slice(0, 8)}`}>{step}</li>
        ))}
      </ol>
    </details>
  );
}
