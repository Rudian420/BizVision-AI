/**
 * Chatbot WebSocket factory.
 *
 * Builds a typed connection to the backend's
 * `/api/v1/chatbot/ws/{conversation_id}?token=<jwt>` endpoint and
 * fans out the four server-event shapes (`token` / `tool_call` /
 * `complete` / `error`) through a single `onEvent` callback.
 *
 * Pure — no React. The `useChatbotStream` hook wraps this in a
 * lifecycle hook with reassembly + cleanup. Keeping the factory
 * separate lets the test suite mock `WebSocket` and verify the
 * client's event dispatch without rendering.
 */

import { WS_ROUTES } from '@bizvision/contracts';

import { env } from '@/lib/env';

/** Server → client event shapes from `routes/chatbot.py`. */
export type WsServerEvent =
  | { type: 'token'; content: string; agent_step?: string }
  | { type: 'tool_call'; tool: string; status?: string }
  | {
      type: 'complete';
      content: string;
      conversation_id?: string;
      message_id?: string;
      reasoning_trace?: string[];
      sources?: Array<{
        module: string;
        reference_id: string;
        summary: string;
      }>;
    }
  | { type: 'error'; message?: string };

export type WsClientMessage = {
  type: 'message';
  content: string;
  context?: { include_modules?: string[] };
};

export type ChatbotWsHandlers = {
  /** Fires after the underlying `WebSocket.onopen`. */
  onOpen?: () => void;
  /** Single dispatch point for every server event. */
  onEvent?: (event: WsServerEvent) => void;
  /** Fires on any error (parse failure, network drop, server error). */
  onError?: (error: Error) => void;
  /** Fires after the underlying `WebSocket.onclose`. */
  onClose?: (code: number, reason: string) => void;
};

export type ChatbotWsClient = {
  /** Send a user message — must be called after `onOpen` fires. */
  send: (message: WsClientMessage) => void;
  /** True if the socket is open and ready for sends. */
  isOpen: () => boolean;
  /** Close the socket from the client side. */
  close: () => void;
};

/**
 * Convert the configured API base URL (`http(s)://host/api/v1`) into a
 * WebSocket URL (`ws(s)://host/api/v1`). The dedicated
 * `NEXT_PUBLIC_WS_URL` env var doesn't carry the API prefix our
 * routes are mounted under, so deriving from the API URL is the
 * deterministic path. Exported for test coverage.
 */
export function buildWsBaseUrl(apiUrl: string = env.NEXT_PUBLIC_API_URL): string {
  // Trim a trailing slash so the route join below doesn't double up.
  const trimmed = apiUrl.replace(/\/$/, '');
  if (trimmed.startsWith('https://')) return 'wss://' + trimmed.slice('https://'.length);
  if (trimmed.startsWith('http://')) return 'ws://' + trimmed.slice('http://'.length);
  // Already a ws / wss URL — pass through.
  return trimmed;
}

/** Build the full chatbot WS URL given an active conversation + access token. */
export function buildChatbotWsUrl(conversationId: string, token: string): string {
  const base = buildWsBaseUrl();
  const path = WS_ROUTES.chatbot(conversationId);
  // The backend's WS handler takes the JWT as a `?token=` query param —
  // browser WebSocket clients cannot set custom request headers.
  const query = `?token=${encodeURIComponent(token)}`;
  return `${base}${path}${query}`;
}

/**
 * Open a chatbot WebSocket and dispatch incoming events through
 * `handlers`. Returns a small client object so the caller can `send`
 * messages and `close` the connection.
 *
 * The factory hides the raw `WebSocket` from callers so a future
 * swap to a polyfill or transport upgrade only touches this file.
 */
export function openChatbotWs(
  conversationId: string,
  token: string,
  handlers: ChatbotWsHandlers = {},
  /**
   * Constructor override — production passes the browser's global
   * WebSocket; tests inject a mock implementation.
   */
  WsCtor: typeof WebSocket = typeof WebSocket !== 'undefined' ? WebSocket : (undefined as never),
): ChatbotWsClient {
  if (!WsCtor) {
    throw new Error('WebSocket is unavailable in this environment.');
  }
  const url = buildChatbotWsUrl(conversationId, token);
  const ws = new WsCtor(url);

  ws.onopen = () => {
    handlers.onOpen?.();
  };

  ws.onmessage = (event: MessageEvent) => {
    try {
      const parsed = JSON.parse(String(event.data)) as WsServerEvent;
      if (parsed && typeof parsed === 'object' && 'type' in parsed) {
        handlers.onEvent?.(parsed);
      } else {
        handlers.onError?.(new Error('Unrecognised WebSocket payload shape.'));
      }
    } catch (err) {
      handlers.onError?.(err instanceof Error ? err : new Error('JSON parse failure.'));
    }
  };

  ws.onerror = () => {
    handlers.onError?.(new Error('WebSocket connection error.'));
  };

  ws.onclose = (event: CloseEvent) => {
    handlers.onClose?.(event.code, event.reason);
  };

  return {
    send: (message: WsClientMessage) => {
      if (ws.readyState !== ws.OPEN) {
        handlers.onError?.(
          new Error(`Cannot send: socket state is ${ws.readyState}, expected OPEN.`),
        );
        return;
      }
      ws.send(JSON.stringify(message));
    },
    isOpen: () => ws.readyState === ws.OPEN,
    close: () => {
      // Use `close()` (not `terminate()`) so the server's handler
      // sees a clean disconnect and runs its `WebSocketDisconnect`
      // catch block.
      if (ws.readyState === ws.OPEN || ws.readyState === ws.CONNECTING) {
        ws.close();
      }
    },
  };
}
