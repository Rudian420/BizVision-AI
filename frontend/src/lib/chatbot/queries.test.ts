/**
 * `chatbotKeys` factory tests — pure references, no React Query.
 *
 * The hooks themselves are exercised by the wave-2 e2e suite; the
 * key factory is the load-bearing surface for cache invalidation.
 */

import { describe, expect, it } from 'vitest';

import { chatbotKeys } from './queries';

describe('chatbotKeys', () => {
  it('exposes a stable namespace root', () => {
    expect(chatbotKeys.all).toEqual(['chatbot']);
  });

  it('builds a stable paged conversations key', () => {
    expect(chatbotKeys.conversations(1, 20)).toEqual(['chatbot', 'conversations', 1, 20]);
  });

  it('distinguishes pages so the cache doesn’t collide across pagination', () => {
    expect(chatbotKeys.conversations(1, 20)).not.toEqual(chatbotKeys.conversations(2, 20));
    expect(chatbotKeys.conversations(1, 20)).not.toEqual(chatbotKeys.conversations(1, 10));
  });

  it('builds a stable per-conversation key', () => {
    expect(chatbotKeys.conversation('abc-123')).toEqual([
      'chatbot',
      'conversation',
      'abc-123',
    ]);
  });

  it('replaces a null id with a sentinel so React Query keys remain hashable', () => {
    const key = chatbotKeys.conversation(null);
    expect(key.every((segment) => segment !== null)).toBe(true);
  });

  it('all conversation keys share the root', () => {
    const id = chatbotKeys.conversation('x')[0];
    const list = chatbotKeys.conversations(1, 20)[0];
    expect(id).toBe(list);
    expect(id).toBe(chatbotKeys.all[0]);
  });

  // TASK-034: audit-feed deep-link query keys.
  it('namespaces message-detail keys distinctly from conversation keys', () => {
    expect(chatbotKeys.messageDetail('msg-1')).toEqual([
      'chatbot',
      'messages',
      'detail',
      'msg-1',
    ]);
    expect(JSON.stringify(chatbotKeys.messageDetail('x'))).not.toBe(
      JSON.stringify(chatbotKeys.conversation('x')),
    );
  });

  it('namespaces executive-report-detail keys under their own segment', () => {
    expect(chatbotKeys.executiveReportDetail('er-1')).toEqual([
      'chatbot',
      'executive-reports',
      'detail',
      'er-1',
    ]);
  });

  it('isolates message-detail and report-detail by id', () => {
    expect(JSON.stringify(chatbotKeys.messageDetail('a'))).not.toBe(
      JSON.stringify(chatbotKeys.messageDetail('b')),
    );
    expect(JSON.stringify(chatbotKeys.executiveReportDetail('a'))).not.toBe(
      JSON.stringify(chatbotKeys.executiveReportDetail('b')),
    );
  });
});
