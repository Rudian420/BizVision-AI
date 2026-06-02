'use client';

import { useState, type FormEvent } from 'react';

import { FormField } from '@/components/auth/FormField';
import type {
  CandidateInput,
  ExperienceLevel,
  RecruitmentAnalysisRequest,
  UploadFileResult,
} from '@/lib/recruitment/types';

import { CVUploadDropzone, uploadResultToCandidate } from './CVUploadDropzone';
import { TextArea } from './TextArea';

const EXPERIENCE_LEVELS: ExperienceLevel[] = ['entry', 'mid', 'senior', 'lead', 'executive'];

type AnalyzeFormProps = {
  /** Called with a validated request payload when the form submits. */
  onSubmit: (request: RecruitmentAnalysisRequest) => void;
  submitting: boolean;
};

export function AnalyzeForm({ onSubmit, submitting }: AnalyzeFormProps) {
  const [jobTitle, setJobTitle] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [requiredSkills, setRequiredSkills] = useState('');
  const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel>('senior');
  const [candidateText, setCandidateText] = useState('');
  const [uploadedCandidates, setUploadedCandidates] = useState<CandidateInput[]>([]);
  const [anonymise, setAnonymise] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function handleUploadParsed(results: UploadFileResult[]) {
    // Accept only files that parsed cleanly + have non-empty cv_text.
    // The dropzone already renders error rows; the candidate list
    // doesn't need to know about them.
    const next = results
      .filter((r) => !r.error && r.cv_text.trim().length > 0)
      .map((r, i) => uploadResultToCandidate(r, uploadedCandidates.length + i));
    if (next.length === 0) return;
    setUploadedCandidates((prev) => [...prev, ...next]);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setError(null);

    // Combine textarea-typed candidates with files parsed via the
    // dropzone — both sources flow into the same `/analyze` call.
    const textCandidates = parseCandidateBlocks(candidateText);
    const candidates = mergeCandidates(textCandidates, uploadedCandidates);

    if (candidates.length === 0) {
      setError(
        'Add at least one candidate — paste CVs in the textarea or upload a PDF / DOCX.',
      );
      return;
    }
    if (jobDescription.trim().length < 50) {
      setError('Job description must be at least 50 characters.');
      return;
    }

    const request: RecruitmentAnalysisRequest = {
      job_description: {
        title: jobTitle.trim(),
        description: jobDescription.trim(),
        required_skills: parseSkills(requiredSkills),
        experience_level: experienceLevel,
      },
      candidates,
      anonymize_names: anonymise,
      top_k: candidates.length,
    };
    onSubmit(request);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <FormField
        label="Job title"
        type="text"
        name="job_title"
        required
        minLength={3}
        value={jobTitle}
        onChange={(e) => setJobTitle(e.target.value)}
      />
      <TextArea
        label="Job description"
        name="job_description"
        rows={6}
        required
        hint="≥ 50 characters"
        value={jobDescription}
        onChange={(e) => setJobDescription(e.target.value)}
      />
      <FormField
        label="Required skills (comma-separated)"
        type="text"
        name="required_skills"
        placeholder="python, sql, distributed systems"
        value={requiredSkills}
        onChange={(e) => setRequiredSkills(e.target.value)}
      />

      <div className="mb-4">
        <label
          htmlFor="experience_level"
          className="mb-1 block font-ui text-xs uppercase tracking-wider text-text-secondary"
        >
          Experience level
        </label>
        <select
          id="experience_level"
          name="experience_level"
          value={experienceLevel}
          onChange={(e) => setExperienceLevel(e.target.value as ExperienceLevel)}
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-ui text-sm text-text-primary outline-none transition focus:border-cyan focus:ring-1 focus:ring-cyan/40"
        >
          {EXPERIENCE_LEVELS.map((level) => (
            <option key={level} value={level}>
              {level.charAt(0).toUpperCase() + level.slice(1)}
            </option>
          ))}
        </select>
      </div>

      <CVUploadDropzone
        onParsed={handleUploadParsed}
        alreadyAdded={uploadedCandidates.length}
      />

      <TextArea
        label="Candidate CVs (or paste manually)"
        name="candidates"
        rows={8}
        hint="Separate candidates with a blank line. Uploaded files merge with anything you paste here."
        placeholder={
          'Jane Doe\n8 years Python, FastAPI, ML systems...\n\nJohn Smith\n5 years backend, AWS, microservices...'
        }
        value={candidateText}
        onChange={(e) => setCandidateText(e.target.value)}
      />

      <label className="mb-4 flex items-center gap-2 font-ui text-sm text-text-secondary">
        <input
          type="checkbox"
          checked={anonymise}
          onChange={(e) => setAnonymise(e.target.checked)}
          className="h-4 w-4 rounded border-white/20 bg-white/5 accent-cyan"
        />
        <span>Anonymise candidate names (recommended — reduces name-based bias)</span>
      </label>

      {error && (
        <p
          role="alert"
          className="mb-2 rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-xs text-coral"
        >
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-cyan px-4 py-2 font-ui text-sm font-medium text-void shadow-glow-cyan transition hover:bg-cyan/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? 'Ranking candidates…' : 'Run analysis'}
      </button>
    </form>
  );
}

// ── Helpers ────────────────────────────────────────────────────────

/** Combine textarea-typed candidates with file-upload candidates,
 * de-duplicating by `candidate_id`. Manual paste wins on collision
 * (the user just-typed wins over an earlier upload with the same
 * synthetic id). Pure function for testability. */
export function mergeCandidates(
  fromText: CandidateInput[],
  fromUpload: CandidateInput[],
): CandidateInput[] {
  const seen = new Set<string>();
  const out: CandidateInput[] = [];
  for (const c of [...fromText, ...fromUpload]) {
    if (seen.has(c.candidate_id)) continue;
    seen.add(c.candidate_id);
    out.push(c);
  }
  return out;
}

/** Split a comma-separated string into trimmed, non-empty skills. */
export function parseSkills(raw: string): string[] {
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/**
 * Split the candidate textarea into one `CandidateInput` per
 * blank-line-separated block. The first line of each block is the
 * candidate's name; subsequent lines are the CV body.
 *
 * The candidate_id is generated deterministically from the block
 * index so reloads or re-submits produce stable identifiers.
 */
export function parseCandidateBlocks(raw: string): CandidateInput[] {
  const blocks = raw
    .split(/\n\s*\n/) // blank line separator (tolerates whitespace-only lines)
    .map((block) => block.trim())
    .filter((block) => block.length > 0);

  return blocks.map((block, idx) => {
    const lines = block.split('\n');
    const firstLine = lines[0]?.trim() ?? '';
    const looksLikeName = firstLine.length > 0 && firstLine.length < 80 && !firstLine.match(/[.,]/);
    const name = looksLikeName ? firstLine : null;
    const cv_text = looksLikeName ? lines.slice(1).join('\n').trim() : block;
    return {
      candidate_id: `cand-${idx + 1}`,
      name,
      cv_text,
    };
  });
}
