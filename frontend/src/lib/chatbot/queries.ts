/**
 * React Query hooks for the chatbot module.
 *
 * Wave 1: send-message mutation + paged conversation list query +
 * single-conversation history query. Each uses a stable
 * `queryKeys.*` factory so cache invalidation after a send is
 * one-line surgical.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchExecutiveReportDetail,
  fetchMessageDetail,
  getConversation,
  listConversations,
  sendMessage,
} from './client';
import type {
  ChatbotExecutiveReportDetail,
  ChatbotMessageDetail,
  ChatMessageRequest,
  ChatMessageResponse,
  ConversationHistoryResponse,
  ConversationListResponse,
} from './types';

export const chatbotKeys = {
  all: ['chatbot'] as const,
  conversations: (page: number, pageSize: number) =>
    [...chatbotKeys.all, 'conversations', page, pageSize] as const,
  conversation: (id: string | null) =>
    [...chatbotKeys.all, 'conversation', id ?? '(none)'] as const,
  messageDetail: (messageId: string) =>
    [...chatbotKeys.all, 'messages', 'detail', messageId] as const,
  executiveReportDetail: (reportId: string) =>
    [...chatbotKeys.all, 'executive-reports', 'detail', reportId] as const,
};

export function useSendMessageMutation() {
  const queryClient = useQueryClient();
  return useMutation<ChatMessageResponse, Error, ChatMessageRequest>({
    mutationFn: sendMessage,
    onSuccess: (data, vars) => {
      // Invalidate the paged list (a new conversation may have been
      // created; an existing one's `updated_at` definitely bumped).
      queryClient.invalidateQueries({ queryKey: chatbotKeys.all });
      // And refresh the active conversation's turn list explicitly so
      // the thread shows the new pair without a manual refetch.
      const conversationId = vars.conversation_id ?? data.conversation_id;
      queryClient.invalidateQueries({
        queryKey: chatbotKeys.conversation(conversationId),
      });
    },
  });
}

export function useConversationsQuery(page: number = 1, pageSize: number = 20) {
  return useQuery<ConversationListResponse>({
    queryKey: chatbotKeys.conversations(page, pageSize),
    queryFn: () => listConversations(page, pageSize),
  });
}

export function useConversationQuery(conversationId: string | null) {
  return useQuery<ConversationHistoryResponse>({
    queryKey: chatbotKeys.conversation(conversationId),
    queryFn: () => {
      if (!conversationId) {
        return Promise.reject(new Error('No conversation selected'));
      }
      return getConversation(conversationId);
    },
    enabled: !!conversationId,
  });
}

export function useChatbotMessageDetailQuery(messageId: string | null) {
  return useQuery<ChatbotMessageDetail>({
    queryKey: chatbotKeys.messageDetail(messageId ?? ''),
    queryFn: () => {
      if (!messageId) throw new Error('messageId required');
      return fetchMessageDetail(messageId);
    },
    enabled: Boolean(messageId),
    staleTime: 60_000,
  });
}

export function useExecutiveReportDetailQuery(reportId: string | null) {
  return useQuery<ChatbotExecutiveReportDetail>({
    queryKey: chatbotKeys.executiveReportDetail(reportId ?? ''),
    queryFn: () => {
      if (!reportId) throw new Error('reportId required');
      return fetchExecutiveReportDetail(reportId);
    },
    enabled: Boolean(reportId),
    staleTime: 60_000,
  });
}
