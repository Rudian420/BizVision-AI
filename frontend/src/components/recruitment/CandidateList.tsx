'use client';

import type { CandidateRankingResult } from '@/lib/recruitment/types';

import { CandidateRow } from './CandidateRow';

type CandidateListProps = {
  candidates: CandidateRankingResult[];
};

export function CandidateList({ candidates }: CandidateListProps) {
  if (!candidates || candidates.length === 0) {
    return (
      <p className="rounded-lg border border-white/10 bg-white/[0.02] px-4 py-6 text-center font-ui text-sm text-text-secondary">
        No candidates returned for this analysis.
      </p>
    );
  }

  return (
    <ul aria-label="Ranked candidates" className="space-y-3">
      {candidates.map((c) => (
        <CandidateRow key={c.candidate_id} candidate={c} />
      ))}
    </ul>
  );
}
