import type { Metadata } from 'next';

import { ForecastHistoryWorkspace } from '@/components/forecasting/ForecastHistoryWorkspace';

export const metadata: Metadata = { title: 'Forecasting · Forecasts History' };

export default function ForecastingForecastsPage() {
  return <ForecastHistoryWorkspace />;
}
