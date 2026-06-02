'use client';

import { useEffect, useRef } from 'react';

import type { ToolCallNotice } from '@/hooks/use-chatbot-stream';
import type { ChatMessageResponse, ChatTurn } from '@/lib/chatbot/types';

import { MessageBubble } from './MessageBubble';
import { StreamingAssistantBubble } from './StreamingAssistantBubble';

type MessageThreadProps = {
  /** Persisted history from `GET /chatbot/conversations/{id}`. */
  turns: ChatTurn[];
  /** Most recent assistant response from `POST /chatbot/message`.
   *  Surfaced inline at the bottom of the thread alongside the
   *  persisted turns so reasoning trace + sources are visible
   *  immediately, before the React Query refetch overwrites it. */
  latestResponse?: ChatMessageResponse | null;
  /**
   * True while the REST send-message mutation is in flight; renders
   * the static "thinking" placeholder. Mutually exclusive in practice
   * with `isStreaming` — the workspace picks one path per send.
   */
  isPending?: boolean;
  /**
   * In-flight WebSocket stream state. When `isStreaming` is true the
   * thread renders a `<StreamingAssistantBubble>` instead of the
   * REST-style placeholder, fed by the running `streamingContent` +
   * tool-call notices.
   */
  isStreaming?: boolean;
  streamingContent?: string;
  toolCalls?: ToolCallNotice[];
};

/**
 * Scrollable conversation thread.
 *
 * Auto-scrolls to the latest message on every render (cheap effect —
 * the ref points at the bottom sentinel). Routes the in-flight state
 * to either a streaming-aware bubble (`isStreaming` + WS path) or the
 * static REST-mode placeholder.
 */
export function MessageThread({
  turns,
  latestResponse,
  isPending,
  isStreaming,
  streamingContent,
  toolCalls,
}: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // PERF (TASK-039): during streaming, content updates per token. A
  // `behavior: 'smooth'` scroll launches a new animation each tick and
  // they overlap, producing jitter + wasted main-thread work. Swap to
  // `'auto'` (instant snap) while streaming so the bottom sticks
  // cleanly, and coalesce via rAF so multiple state updates in the
  // same frame produce one paint instead of N.
  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({
        behavior: isStreaming ? 'auto' : 'smooth',
        block: 'end',
      });
    });
    return () => cancelAnimationFrame(raf);
  }, [
    turns.length,
    latestResponse?.message_id,
    isPending,
    isStreaming,
    streamingContent,
  ]);

  const hasContent =
    turns.length > 0 || !!latestResponse || isPending || isStreaming;

  if (!hasContent) {
    return (
      <div
        role="status"
        className="flex h-full min-h-[200px] items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.02] px-6 text-center font-ui text-sm text-text-secondary"
      >
        Ask the AI advisor anything — about hiring, pricing, profit,
        ESG, or strategy across modules.
      </div>
    );
  }

  // Skip the *last* persisted assistant turn when an in-flight
  // `latestResponse` is present, to avoid showing the same content
  // twice (it'll be the same once persistence catches up).
  const showLatest = !!latestResponse;
  const persisted = showLatest && turns.length > 0 && turns[turns.length - 1].role === 'assistant'
    ? turns.slice(0, -1)
    : turns;

  return (
    <div className="max-h-[60vh] min-h-[200px] overflow-y-auto pr-2">
      <ul aria-label="Conversation thread">
        {persisted.map((turn, i) => (
          <MessageBubble
            key={`turn-${i}-${turn.created_at}`}
            role={turn.role}
            content={turn.content}
            createdAt={turn.created_at}
          />
        ))}

        {showLatest && latestResponse && (
          <MessageBubble
            key={`latest-${latestResponse.message_id}`}
            role="assistant"
            content={latestResponse.content}
            createdAt={latestResponse.created_at}
            reasoningTrace={latestResponse.reasoning_trace}
            sources={latestResponse.sources}
          />
        )}

        {isStreaming && (
          <StreamingAssistantBubble
            content={streamingContent ?? ''}
            toolCalls={toolCalls ?? []}
          />
        )}

        {isPending && !isStreaming && (
          <li className="my-3 flex justify-start">
            <span
              role="status"
              aria-live="polite"
              className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.02] px-4 py-2 font-ui text-sm text-text-secondary"
            >
              <span aria-hidden className="inline-flex gap-1">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-coral" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-coral/70" style={{ animationDelay: '120ms' }} />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-coral/40" style={{ animationDelay: '240ms' }} />
              </span>
              The advisor is thinking…
            </span>
          </li>
        )}
      </ul>
      <div ref={bottomRef} aria-hidden />
    </div>
  );
}
