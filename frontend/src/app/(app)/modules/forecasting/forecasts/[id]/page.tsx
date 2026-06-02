import type { Metadata } from 'next';

import { ForecastDetailWorkspace } from '@/components/forecasting/ForecastDetailWorkspace';

export const metadata: Metadata = { title: 'Forecasting · Forecast Detail' };

export default function ForecastDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return <ForecastDetailWorkspace forecastId={params.id} />;
}
