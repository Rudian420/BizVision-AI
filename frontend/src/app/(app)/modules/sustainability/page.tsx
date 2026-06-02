import type { Metadata } from 'next';

import { SustainabilityWorkspace } from '@/components/sustainability/SustainabilityWorkspace';

export const metadata: Metadata = { title: 'Green Business Scorer' };

export default function SustainabilityPage() {
  return <SustainabilityWorkspace />;
}
