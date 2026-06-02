import type { Metadata } from 'next';
import { Suspense } from 'react';

import { ChatbotWorkspace } from '@/components/chatbot/ChatbotWorkspace';

export const metadata: Metadata = { title: 'Financial Advisory AI' };

export default function ChatbotPage() {
  // Suspense boundary: ChatbotWorkspace reads `?conversation_id=` via
  // useSearchParams() to honour audit-feed deep-links (TASK-034). Next
  // requires the consumer to live under a Suspense boundary so the
  // statically-rendered shell can stream the dynamic search-param read.
  return (
    <Suspense fallback={<ChatbotWorkspaceFallback />}>
      <ChatbotWorkspace />
    </Suspense>
  );
}

function ChatbotWorkspaceFallback() {
  return (
    <div
      aria-hidden
      className="h-64 animate-pulse rounded-2xl border border-white/10 bg-white/[0.02]"
    />
  );
}
