import type { Metadata } from 'next';

import { SustainabilityHistoryWorkspace } from '@/components/sustainability/SustainabilityHistoryWorkspace';

export const metadata: Metadata = { title: 'Sustainability · Assessments History' };

export default function SustainabilityAssessmentsPage() {
  return <SustainabilityHistoryWorkspace />;
}
