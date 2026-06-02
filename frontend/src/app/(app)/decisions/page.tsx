import type { Metadata } from 'next';

import { DecisionFeedWorkspace } from '@/components/audits/DecisionFeedWorkspace';

export const metadata: Metadata = { title: 'ML Decision Feed' };

export default function DecisionsPage() {
  return <DecisionFeedWorkspace />;
}
