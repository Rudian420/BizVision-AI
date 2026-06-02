import type { Metadata } from 'next';

import { PricingWorkspace } from '@/components/pricing/PricingWorkspace';

export const metadata: Metadata = { title: 'Smart Pricing Advisor' };

export default function PricingPage() {
  return <PricingWorkspace />;
}
