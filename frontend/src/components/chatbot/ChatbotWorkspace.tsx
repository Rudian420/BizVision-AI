'use client';

import { useSearchParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { useChatbotStream } from '@/hooks/use-chatbot-stream';
import { formatAuthError } from '@/lib/auth/errors';
import {
  chatbotKeys,
  useConversationQuery,
  useConversationsQuery,
  useSendMessageMutation,
} from '@/lib/chatbot/queries';
import type { ChatMessageRequest, ChatMessageResponse } from '@/lib/chatbot/types';
import { moduleById } from '@/lib/modules';
import { useQueryClient } from '@tanstack/react-query';

import { ChatComposer } from './ChatComposer';
import { ConversationHistoryList } from './ConversationHistoryList';
import { MessageThread } from './MessageThread';

/**
 * Chatbot workspace — the last frontend module UI (FE-015).
 *
 * Two-column layout (matching the rest of the module UIs): message
 * thread + composer on the left, conversation history rail on the
 * right. Stacks on narrow viewports. State management:
 *
 *   • `activeConversationId` is the currently-loaded thread (null
 *     means "new conversation"). Bumped by:
 *       – the history rail's onSelect → switch to an existing thread
 *       – the composer's first send when no thread is active →
 *         lock to the new conversation_id returned by the API
 *       – the "+ new" button → reset to null
 *   • `latestResponse` mirrors the most recent assistant response
 *     so the reasoning trace + sources render *immediately* below
 *     the persisted history, before the conversation refetch catches
 *     up. Sourced from REST mutation result on first send + from the
 *     WS `complete` event on follow-up sends.
 *
 * **WebSocket streaming (TASK-027)**: the backend's WS handler
 * requires an existing `conversation_id` in the URL, so the
 * workspace routes by `activeConversationId`:
 *   – null  → REST `useSendMessageMutation` (creates the conversation)
 *   – set   → WS `useChatbotStream` (token-by-token streaming)
 *
 * On the WS path, the `lastComplete` event surfaces through the same
 * `latestResponse` mirror so the rest of the thread renders unchanged
 * once the streaming bubble hands off.
 */
export function ChatbotWorkspace() {
  const meta = moduleById('chatbot');
  const searchParams = useSearchParams();

  // Deep-link entry (TASK-034): the audit feed redirects to
  // `/modules/chatbot?conversation_id={id}` so the workspace can
  // load that conversation on mount without a manual click in the
  // history rail. The deep-link value is consumed once via a ref
  // so subsequent navigations inside the workspace aren't
  // hijacked back to the URL state.
  const deepLinkConversationId = searchParams.get('conversation_id');
  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    deepLinkConversationId,
  );
  const [latestResponse, setLatestResponse] = useState<ChatMessageResponse | null>(null);
  const deepLinkConsumed = useRef(Boolean(deepLinkConversationId));

  // If the URL param changes mid-session (e.g. the user clicks
  // another audit row's deep-link without unmounting the workspace),
  // honour it once.
  useEffect(() => {
    if (deepLinkConversationId && !deepLinkConsumed.current) {
      setActiveConversationId(deepLinkConversationId);
      deepLinkConsumed.current = true;
    }
  }, [deepLinkConversationId]);

  const queryClient = useQueryClient();
  const conversationsQuery = useConversationsQuery(1, 20);
  const threadQuery = useConversationQuery(activeConversationId);
  const sendMutation = useSendMessageMutation();
  const stream = useChatbotStream(activeConversationId);

  // When the active conversation changes, clear any stale in-flight
  // response — it belonged to the old thread.
  useEffect(() => {
    setLatestResponse(null);
  }, [activeConversationId]);

  // When a WS `complete` event arrives, mirror it into
  // `latestResponse` so the persisted-history-style bubble renders
  // its reasoning trace + sources, then consume the stream's hand-off
  // state to clear the in-flight bubble. Also invalidate the React
  // Query caches so the right-rail freshness pip + thread refetch
  // both update — same posture as the REST mutation's onSuccess.
  useEffect(() => {
    if (!stream.lastComplete) return;
    const complete = stream.lastComplete;
    setLatestResponse({
      conversation_id: complete.conversation_id ?? activeConversationId ?? '',
      message_id: complete.message_id ?? '',
      content: complete.content,
      created_at: new Date().toISOString(),
      reasoning_trace: complete.reasoning_trace ?? [],
      sources: complete.sources ?? [],
      tokens_used: 0,
    });
    stream.consumeComplete();
    queryClient.invalidateQueries({ queryKey: chatbotKeys.all });
    if (activeConversationId) {
      queryClient.invalidateQueries({
        queryKey: chatbotKeys.conversation(activeConversationId),
      });
    }
  }, [stream, activeConversationId, queryClient]);

  function handleSend(request: ChatMessageRequest) {
    // Streaming path — follow-up send on an existing conversation.
    if (activeConversationId && stream.isReady) {
      setLatestResponse(null);
      stream.send(request.content, request.include_modules ?? []);
      return;
    }
    // REST path — first send (creates the conversation). After the
    // server returns a conversation_id, the WS lifecycle effect
    // automatically opens the socket for subsequent sends.
    sendMutation.mutate(request, {
      onSuccess: (data) => {
        setLatestResponse(data);
        if (!request.conversation_id) {
          setActiveConversationId(data.conversation_id);
        }
      },
    });
  }

  function handleSelectConversation(id: string) {
    setActiveConversationId(id);
    sendMutation.reset();
  }

  function handleNewConversation() {
    setActiveConversationId(null);
    setLatestResponse(null);
    sendMutation.reset();
  }

  const errorMessage = sendMutation.isError
    ? formatAuthError(sendMutation.error)
    : stream.error;

  return (
    <div>
      <header className="mb-8 border-b border-white/10 pb-6">
        <div className="mb-2 flex items-center gap-3">
          <span className="font-data text-3xl" style={{ color: meta.accent }}>
            {meta.glyph}
          </span>
          <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            {meta.id} module
          </span>
        </div>
        <h2 className="font-ui text-3xl font-semibold tracking-tight text-text-primary">
          {meta.label}
        </h2>
        <p className="mt-2 font-ui text-sm text-text-secondary">{meta.tagline}</p>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,_1fr)_minmax(0,_320px)]">
        <section
          aria-label="Active conversation"
          className="flex min-h-[50vh] flex-col gap-4 rounded-2xl border border-white/10 bg-white/[0.02] p-5"
        >
          {errorMessage && (
            <p
              role="alert"
              className="rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-sm text-coral"
            >
              {errorMessage}
            </p>
          )}

          <MessageThread
            turns={threadQuery.data?.turns ?? []}
            latestResponse={latestResponse}
            isPending={sendMutation.isPending}
            isStreaming={stream.isStreaming}
            streamingContent={stream.streamingContent}
            toolCalls={stream.toolCalls}
          />

          <ChatComposer
            conversationId={activeConversationId}
            onSubmit={handleSend}
            submitting={sendMutation.isPending || stream.isStreaming}
          />
        </section>

        <ConversationHistoryList
          conversations={conversationsQuery.data?.items ?? []}
          activeId={activeConversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          isLoading={conversationsQuery.isLoading}
          isError={conversationsQuery.isError}
        />
      </div>
    </div>
  );
}
