import type { Metadata } from 'next';

import { SessionsHistoryWorkspace } from '@/components/recruitment/SessionsHistoryWorkspace';

export const metadata: Metadata = { title: 'Recruitment · Session History' };

export default function RecruitmentSessionsPage() {
  return <SessionsHistoryWorkspace />;
}
