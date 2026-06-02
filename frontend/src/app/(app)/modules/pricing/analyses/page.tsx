import type { Metadata } from 'next';

import { PricingHistoryWorkspace } from '@/components/pricing/PricingHistoryWorkspace';

export const metadata: Metadata = { title: 'Pricing · Analyses History' };

export default function PricingAnalysesPage() {
  return <PricingHistoryWorkspace />;
}
