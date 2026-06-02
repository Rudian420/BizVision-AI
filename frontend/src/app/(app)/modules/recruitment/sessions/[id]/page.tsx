import type { Metadata } from 'next';

import { SessionDetailWorkspace } from '@/components/recruitment/SessionDetailWorkspace';

export const metadata: Metadata = { title: 'Recruitment · Session Detail' };

export default function RecruitmentSessionDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return <SessionDetailWorkspace sessionId={params.id} />;
}
