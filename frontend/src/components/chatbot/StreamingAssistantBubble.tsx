'use client';

import type { ToolCallNotice } from '@/hooks/use-chatbot-stream';
import { cn } from '@/lib/utils';

type StreamingAssistantBubbleProps = {
  /** Running concatenation of token chunks (cleared per turn by the hook). */
  content: string;
  /** Captured tool_call events for the current turn. */
  toolCalls: ToolCallNotice[];
};

/**
 * In-flight assistant bubble fed by the WebSocket stream.
 *
 * Mirrors `MessageBubble role="assistant"` visually so the user
 * doesn't see a layout shift when the `complete` event hands the
 * turn off to the persisted bubble. While streaming we surface
 * a blinking caret at the content tail to make the typewriter
 * effect explicit, plus a strip of tool-call chips that grows as
 * the agent invokes its internal tools.
 */
export function StreamingAssistantBubble({ content, toolCalls }: StreamingAssistantBubbleProps) {
  const railColour = '#FF3B6B';

  return (
    <li className="my-3 flex justify-start">
      <article
        className={cn(
          'max-w-[80%] rounded-2xl rounded-bl-sm border border-white/10 bg-white/[0.02] px-4 py-3',
        )}
        style={{ boxShadow: `inset 3px 0 0 ${railColour}` }}
      >
        <header className="mb-1 flex items-baseline justify-between gap-3 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          <span>Assistant</span>
          <span className="font-data normal-case text-coral">streaming…</span>
        </header>

        <p className="font-ui text-sm leading-relaxed text-text-primary">
          {content}
          {/* Blinking caret — purely decorative; aria-hidden so screen
              readers don't announce a literal pipe character. */}
          <span
            aria-hidden
            className="ml-0.5 inline-block h-3 w-[2px] animate-pulse bg-coral align-middle"
          />
        </p>

        {toolCalls.length > 0 && (
          <ul
            aria-label="Agent tool calls"
            className="mt-3 flex flex-wrap gap-1.5"
          >
            {toolCalls.map((tc) => (
              <li key={tc.seq}>
                <span
                  className="inline-flex items-center gap-1.5 rounded-full border border-coral/40 bg-coral/10 px-2.5 py-1 font-ui text-[11px] uppercase tracking-widest text-coral"
                >
                  <span
                    aria-hidden
                    className="h-1.5 w-1.5 animate-pulse rounded-full bg-coral"
                  />
                  {tc.tool}
                  {tc.status && tc.status !== 'executing' && (
                    <span className="ml-1 text-text-secondary">· {tc.status}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </article>
    </li>
  );
}
