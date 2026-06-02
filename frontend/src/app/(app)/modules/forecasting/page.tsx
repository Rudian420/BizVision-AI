import type { Metadata } from 'next';

import { ForecastingWorkspace } from '@/components/forecasting/ForecastingWorkspace';

export const metadata: Metadata = { title: 'Profit Forecasting' };

export default function ForecastingPage() {
  return <ForecastingWorkspace />;
}
