/**
 * Chatbot API client — wraps `/chatbot/*`.
 *
 * Wave 1 exposes the REST `/message`, `/conversations` (paged), and
 * `/conversations/{id}` paths. WebSocket streaming defers to wave 2.
 */

import { API_ROUTES } from '@bizvision/contracts';

import { apiClient } from '@/lib/api-client';

import type {
  ChatbotExecutiveReportDetail,
  ChatbotMessageDetail,
  ChatMessageRequest,
  ChatMessageResponse,
  ConversationHistoryResponse,
  ConversationListResponse,
} from './types';

export async function sendMessage(body: ChatMessageRequest): Promise<ChatMessageResponse> {
  const res = await apiClient.post<ChatMessageResponse>(
    API_ROUTES.chatbot.message,
    body,
  );
  return res.data;
}

export async function listConversations(
  page: number = 1,
  pageSize: number = 20,
): Promise<ConversationListResponse> {
  const res = await apiClient.get<ConversationListResponse>(
    API_ROUTES.chatbot.conversations,
    { params: { page, page_size: pageSize } },
  );
  return res.data;
}

export async function getConversation(
  conversationId: string,
): Promise<ConversationHistoryResponse> {
  const res = await apiClient.get<ConversationHistoryResponse>(
    `${API_ROUTES.chatbot.conversations}/${conversationId}`,
  );
  return res.data;
}

export async function fetchMessageDetail(
  messageId: string,
): Promise<ChatbotMessageDetail> {
  const res = await apiClient.get<ChatbotMessageDetail>(
    API_ROUTES.chatbot.messageDetail(messageId),
  );
  return res.data;
}

export async function fetchExecutiveReportDetail(
  reportId: string,
): Promise<ChatbotExecutiveReportDetail> {
  const res = await apiClient.get<ChatbotExecutiveReportDetail>(
    API_ROUTES.chatbot.executiveReport(reportId),
  );
  return res.data;
}
