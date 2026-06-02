import type { Metadata } from 'next';

import { RecruitmentWorkspace } from '@/components/recruitment/RecruitmentWorkspace';

export const metadata: Metadata = { title: 'Recruitment Intelligence' };

export default function RecruitmentPage() {
  return <RecruitmentWorkspace />;
}
