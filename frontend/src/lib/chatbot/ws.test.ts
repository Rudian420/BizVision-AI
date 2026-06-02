/**
 * Chatbot WebSocket factory tests — verify URL construction + the
 * event-dispatch path through a mock WebSocket implementation.
 *
 * jsdom doesn't provide a usable `WebSocket`, so every test injects
 * the mock class via the factory's `WsCtor` override.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildChatbotWsUrl,
  buildWsBaseUrl,
  openChatbotWs,
  type ChatbotWsHandlers,
} from './ws';

// ── Mock WebSocket ─────────────────────────────────────────────────

const READY_STATES = { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 } as const;

class MockWebSocket {
  static CONNECTING = READY_STATES.CONNECTING;
  static OPEN = READY_STATES.OPEN;
  static CLOSING = READY_STATES.CLOSING;
  static CLOSED = READY_STATES.CLOSED;

  CONNECTING = READY_STATES.CONNECTING;
  OPEN = READY_STATES.OPEN;
  CLOSING = READY_STATES.CLOSING;
  CLOSED = READY_STATES.CLOSED;

  readyState: number = READY_STATES.CONNECTING;
  url: string;

  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
  }

  /** Test-only: transition the socket to OPEN and fire onopen. */
  __open() {
    this.readyState = READY_STATES.OPEN;
    this.onopen?.(new Event('open'));
  }

  /** Test-only: dispatch a synthetic server message. */
  __deliver(payload: unknown) {
    const data = typeof payload === 'string' ? payload : JSON.stringify(payload);
    this.onmessage?.(new MessageEvent('message', { data }));
  }

  /** Test-only: simulate the server closing the socket. */
  __serverClose(code = 1000, reason = 'normal closure') {
    this.readyState = READY_STATES.CLOSED;
    this.onclose?.(new CloseEvent('close', { code, reason }));
  }

  send(payload: string) {
    this.sent.push(payload);
  }

  close() {
    this.readyState = READY_STATES.CLOSED;
    this.onclose?.(new CloseEvent('close', { code: 1000, reason: 'client close' }));
  }
}

// ── URL builders ───────────────────────────────────────────────────

describe('buildWsBaseUrl', () => {
  it('converts http → ws', () => {
    expect(buildWsBaseUrl('http://localhost:8000/api/v1')).toBe('ws://localhost:8000/api/v1');
  });

  it('converts https → wss', () => {
    expect(buildWsBaseUrl('https://api.example.com/api/v1')).toBe(
      'wss://api.example.com/api/v1',
    );
  });

  it('passes through an already-ws URL', () => {
    expect(buildWsBaseUrl('ws://example/api/v1')).toBe('ws://example/api/v1');
  });

  it('trims a trailing slash so route joins do not double up', () => {
    expect(buildWsBaseUrl('http://host/api/v1/')).toBe('ws://host/api/v1');
  });
});

describe('buildChatbotWsUrl', () => {
  it('includes the conversation id in the path', () => {
    const url = buildChatbotWsUrl('abc-123', 'jwt-token');
    expect(url).toContain('/chatbot/ws/abc-123');
  });

  it('encodes the access token as a query param', () => {
    const url = buildChatbotWsUrl('abc-123', 'token with spaces & symbols');
    expect(url).toContain('?token=');
    expect(url).toContain(encodeURIComponent('token with spaces & symbols'));
  });
});

// ── Event dispatch ─────────────────────────────────────────────────

let lastSocket: MockWebSocket | null;
const SocketCtorMock = vi.fn(function (this: unknown, url: string) {
  const socket = new MockWebSocket(url);
  lastSocket = socket;
  return socket;
});
const SocketCtor = SocketCtorMock as unknown as typeof WebSocket;

beforeEach(() => {
  lastSocket = null;
  SocketCtorMock.mockClear();
});

function openWithHandlers(handlers: ChatbotWsHandlers = {}) {
  return openChatbotWs('abc-123', 'jwt-token', handlers, SocketCtor);
}

describe('openChatbotWs', () => {
  it('constructs a WebSocket with the encoded URL', () => {
    openWithHandlers();
    expect(SocketCtorMock).toHaveBeenCalledOnce();
    expect(lastSocket?.url).toContain('/chatbot/ws/abc-123');
    expect(lastSocket?.url).toContain('?token=jwt-token');
  });

  it('fires onOpen when the socket transitions to OPEN', () => {
    const onOpen = vi.fn();
    openWithHandlers({ onOpen });
    lastSocket?.__open();
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it('dispatches a token event through onEvent', () => {
    const events: unknown[] = [];
    openWithHandlers({ onEvent: (e) => events.push(e) });
    lastSocket?.__open();
    lastSocket?.__deliver({ type: 'token', content: 'Based ', agent_step: 'reasoning' });
    expect(events).toEqual([{ type: 'token', content: 'Based ', agent_step: 'reasoning' }]);
  });

  it('dispatches a tool_call event', () => {
    const events: unknown[] = [];
    openWithHandlers({ onEvent: (e) => events.push(e) });
    lastSocket?.__open();
    lastSocket?.__deliver({ type: 'tool_call', tool: 'rag_retrieve', status: 'executing' });
    expect(events).toEqual([{ type: 'tool_call', tool: 'rag_retrieve', status: 'executing' }]);
  });

  it('dispatches a complete event', () => {
    const events: unknown[] = [];
    openWithHandlers({ onEvent: (e) => events.push(e) });
    lastSocket?.__open();
    lastSocket?.__deliver({
      type: 'complete',
      content: 'Full response',
      reasoning_trace: ['step 1', 'step 2'],
      sources: [{ module: 'pricing', reference_id: 'p-1', summary: 'pricing source' }],
    });
    expect((events[0] as { type: string }).type).toBe('complete');
  });

  it('surfaces a JSON parse failure through onError', () => {
    const onError = vi.fn();
    openWithHandlers({ onError });
    lastSocket?.__open();
    lastSocket?.__deliver('not-json');
    expect(onError).toHaveBeenCalledOnce();
  });

  it('rejects payloads without a type field through onError', () => {
    const onError = vi.fn();
    openWithHandlers({ onError });
    lastSocket?.__open();
    lastSocket?.__deliver({ foo: 'bar' });
    expect(onError).toHaveBeenCalledOnce();
  });

  it('fires onClose when the socket closes', () => {
    const onClose = vi.fn();
    openWithHandlers({ onClose });
    lastSocket?.__open();
    lastSocket?.__serverClose(1006, 'unexpected');
    expect(onClose).toHaveBeenCalledWith(1006, 'unexpected');
  });

  it('isOpen reports true after onOpen fires', () => {
    const client = openWithHandlers();
    expect(client.isOpen()).toBe(false);
    lastSocket?.__open();
    expect(client.isOpen()).toBe(true);
  });

  it('send serialises the message to JSON when open', () => {
    const client = openWithHandlers();
    lastSocket?.__open();
    client.send({ type: 'message', content: 'hello', context: { include_modules: ['pricing'] } });
    expect(lastSocket?.sent).toHaveLength(1);
    const parsed = JSON.parse(lastSocket!.sent[0]);
    expect(parsed).toEqual({
      type: 'message',
      content: 'hello',
      context: { include_modules: ['pricing'] },
    });
  });

  it('send reports onError when the socket is not yet open', () => {
    const onError = vi.fn();
    const client = openWithHandlers({ onError });
    // Note: did not call __open()
    client.send({ type: 'message', content: 'hello' });
    expect(onError).toHaveBeenCalledOnce();
    expect(lastSocket?.sent).toHaveLength(0);
  });

  it('close transitions the socket to CLOSED', () => {
    const client = openWithHandlers();
    lastSocket?.__open();
    client.close();
    expect(lastSocket?.readyState).toBe(READY_STATES.CLOSED);
  });
});
