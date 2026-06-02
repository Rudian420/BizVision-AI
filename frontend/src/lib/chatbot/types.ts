/**
 * Hand-written chatbot contract types.
 *
 * Mirror `backend/src/api/v1/schemas/chatbot.py` + the backend's
 * persistence-layer `list_conversations` shape (TASK-014). Kept
 * local until the OpenAPI generator runs — same posture as the
 * other module type files.
 */

export type ChatRole = 'user' | 'assistant' | 'system';

export type ChatMessageRequest = {
  conversation_id?: string | null;
  content: string;
  include_modules?: string[];
};

export type SourceReference = {
  module: string;
  reference_id: string;
  summary: string;
};

export type ChatMessageResponse = {
  conversation_id: string;
  message_id: string;
  content: string;
  created_at: string;
  reasoning_trace: string[];
  sources: SourceReference[];
  tokens_used: number;
};

export type ChatTurn = {
  role: ChatRole;
  content: string;
  created_at: string;
};

export type ConversationHistoryResponse = {
  conversation_id: string;
  title: string;
  turns: ChatTurn[];
  created_at: string;
};

/**
 * Shape returned by GET /chatbot/conversations (paged). Mirror of
 * `ChatbotService.list_conversations` from TASK-014 — defined here
 * because the backend schema file doesn't (it returns the dict
 * shape directly).
 */
export type ConversationSummary = {
  conversation_id: string;
  title: string;
  message_count: number;
  total_tokens_used: number;
  modules_in_scope: string[];
  model_version: string;
  created_at: string;
  updated_at: string;
};

export type ConversationListResponse = {
  items: ConversationSummary[];
  total: number;
  page: number;
  page_size: number;
};

/** Lightweight detail returned by `/chatbot/messages/{id}` (TASK-034).
 * Resolves a message_id to its parent conversation so the audit-feed
 * deep-link can navigate the user to the chatbot workspace with the
 * right conversation loaded. */
export type ChatbotMessageDetail = {
  message_id: string;
  conversation_id: string;
  conversation_title: string;
  role: ChatRole;
  content: string;
  position: number;
  created_at: string;
};

/** Persisted-row reconstruction returned by
 * `/chatbot/executive-reports/{id}` (TASK-034). */
export type ChatbotExecutiveReportDetail = {
  report_id: string;
  title: string;
  period_label: string;
  modules_included: string[];
  response_payload: Record<string, unknown>;
  model_version: string;
  created_at: string;
};
