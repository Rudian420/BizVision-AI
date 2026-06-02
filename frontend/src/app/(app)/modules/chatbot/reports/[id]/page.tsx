import type { Metadata } from 'next';

import { ExecutiveReportDetailWorkspace } from '@/components/chatbot/ExecutiveReportDetailWorkspace';

export const metadata: Metadata = { title: 'Chatbot · Executive Report' };

export default function ChatbotExecutiveReportPage({
  params,
}: {
  params: { id: string };
}) {
  return <ExecutiveReportDetailWorkspace reportId={params.id} />;
}
