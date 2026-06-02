import type { Metadata } from 'next';

import { PricingAnalysisDetailWorkspace } from '@/components/pricing/PricingAnalysisDetailWorkspace';

export const metadata: Metadata = { title: 'Pricing · Analysis Detail' };

export default function PricingAnalysisDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return <PricingAnalysisDetailWorkspace analysisId={params.id} />;
}
