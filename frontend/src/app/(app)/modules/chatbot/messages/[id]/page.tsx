import type { Metadata } from 'next';

import { MessageDeepLinkLanding } from '@/components/chatbot/MessageDeepLinkLanding';

export const metadata: Metadata = { title: 'Chatbot · Message' };

export default function ChatbotMessageDeepLinkPage({
  params,
}: {
  params: { id: string };
}) {
  return <MessageDeepLinkLanding messageId={params.id} />;
}
