/**
 * `useChatbotStream` — React hook around `openChatbotWs`.
 *
 * Owns the WebSocket lifecycle for a single active conversation
 * (reopens when the active id changes, closes on unmount) and
 * exposes a streaming state machine the UI renders from:
 *
 *   • `streamingContent` — running concatenation of token chunks
 *     for the in-progress assistant turn (cleared at the start of
 *     each send and on `complete`'s mirror handoff).
 *   • `toolCalls` — captured tool_call events for the current turn.
 *   • `isStreaming` — true between `send` and the matching `complete`
 *     (or error).
 *   • `lastComplete` — the most recent `complete` event payload, so
 *     the workspace can mirror it into the persisted-history view
 *     before the conversation refetch catches up.
 *   • `error` — last error message, cleared by the next `send`.
 *
 * The hook gracefully no-ops when no conversation is active (the
 * caller is expected to fall back to the REST mutation for first
 * sends — the backend's WS handler 404s on an unknown conversation
 * id, which we cannot create before the first round-trip).
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  openChatbotWs,
  type ChatbotWsClient,
  type WsServerEvent,
} from '@/lib/chatbot/ws';
import { useAuthStore } from '@/lib/store/use-auth-store';

export type ToolCallNotice = {
  tool: string;
  status: string;
  /** Monotonic counter so React keys stay stable across renders. */
  seq: number;
};

export type StreamCompleteEvent = Extract<WsServerEvent, { type: 'complete' }>;

export type ChatbotStreamState = {
  /** True when an open WS exists for the active conversation. */
  isReady: boolean;
  /** True between a `send` and its matching `complete` (or error). */
  isStreaming: boolean;
  /** Running concatenation of in-flight token chunks. */
  streamingContent: string;
  /** Tool-call notices captured during the current turn. */
  toolCalls: ToolCallNotice[];
  /** Most recent `complete` event payload, or null. */
  lastComplete: StreamCompleteEvent | null;
  /** Last error message (cleared by the next send). */
  error: string | null;
  /** Send a user message via the WS — caller passes a JWT-protected route. */
  send: (content: string, includeModules?: string[]) => void;
  /** Manually clear `lastComplete` after the workspace consumes it. */
  consumeComplete: () => void;
};

export function useChatbotStream(conversationId: string | null): ChatbotStreamState {
  const accessToken = useAuthStore((s) => s.accessToken);

  const [isReady, setReady] = useState(false);
  const [isStreaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [toolCalls, setToolCalls] = useState<ToolCallNotice[]>([]);
  const [lastComplete, setLastComplete] = useState<StreamCompleteEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Imperative refs so the WS event handlers can read up-to-date
  // state without participating in the render dep chain.
  const clientRef = useRef<ChatbotWsClient | null>(null);
  const seqRef = useRef(0);

  // Reset per-turn state — called at the start of every send and
  // whenever the active conversation changes.
  const resetTurn = useCallback(() => {
    setStreaming(false);
    setStreamingContent('');
    setToolCalls([]);
    setLastComplete(null);
  }, []);

  // Open / close the socket when the active conversation changes.
  useEffect(() => {
    // Always start by tearing down the previous socket and resetting
    // the per-turn state.
    if (clientRef.current) {
      clientRef.current.close();
      clientRef.current = null;
    }
    setReady(false);
    resetTurn();
    setError(null);

    if (!conversationId || !accessToken) return;

    const client = openChatbotWs(conversationId, accessToken, {
      onOpen: () => setReady(true),
      onEvent: (event) => {
        if (event.type === 'token') {
          setStreamingContent((prev) => prev + event.content);
        } else if (event.type === 'tool_call') {
          seqRef.current += 1;
          setToolCalls((prev) => [
            ...prev,
            { tool: event.tool, status: event.status ?? 'executing', seq: seqRef.current },
          ]);
        } else if (event.type === 'complete') {
          setLastComplete(event);
          setStreaming(false);
        } else if (event.type === 'error') {
          setError(event.message ?? 'WebSocket reported an error.');
          setStreaming(false);
        }
      },
      onError: (err) => {
        setError(err.message);
        setStreaming(false);
      },
      onClose: () => {
        setReady(false);
      },
    });
    clientRef.current = client;

    return () => {
      client.close();
      clientRef.current = null;
    };
  }, [conversationId, accessToken, resetTurn]);

  const send = useCallback(
    (content: string, includeModules: string[] = []) => {
      const client = clientRef.current;
      if (!client || !client.isOpen()) {
        setError('Chat connection is not ready — try again in a moment.');
        return;
      }
      // Fresh slate for the new turn.
      setStreamingContent('');
      setToolCalls([]);
      setLastComplete(null);
      setError(null);
      setStreaming(true);
      client.send({
        type: 'message',
        content,
        context: includeModules.length > 0 ? { include_modules: includeModules } : undefined,
      });
    },
    [],
  );

  const consumeComplete = useCallback(() => {
    setLastComplete(null);
    setStreamingContent('');
    setToolCalls([]);
  }, []);

  return {
    isReady,
    isStreaming,
    streamingContent,
    toolCalls,
    lastComplete,
    error,
    send,
    consumeComplete,
  };
}
