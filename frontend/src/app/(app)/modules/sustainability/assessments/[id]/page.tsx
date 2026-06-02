import type { Metadata } from 'next';

import { SustainabilityAssessmentDetailWorkspace } from '@/components/sustainability/SustainabilityAssessmentDetailWorkspace';

export const metadata: Metadata = { title: 'Sustainability · Assessment Detail' };

export default function SustainabilityAssessmentDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return <SustainabilityAssessmentDetailWorkspace assessmentId={params.id} />;
}
