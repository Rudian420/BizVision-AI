/**
 * AnalyzeForm parser tests — verifies the candidate-block + skill
 * parsing functions independently of any React rendering. The form
 * component itself is exercised by the wave-2 e2e suite.
 */

import { describe, expect, it } from 'vitest';

import type { CandidateInput } from '@/lib/recruitment/types';

import { mergeCandidates, parseCandidateBlocks, parseSkills } from './AnalyzeForm';

describe('parseSkills', () => {
  it('splits a comma-separated string and trims whitespace', () => {
    expect(parseSkills('python, sql, distributed systems')).toEqual([
      'python',
      'sql',
      'distributed systems',
    ]);
  });

  it('drops empty entries', () => {
    expect(parseSkills('python,,, , sql')).toEqual(['python', 'sql']);
  });

  it('returns an empty array for an empty input', () => {
    expect(parseSkills('')).toEqual([]);
    expect(parseSkills('   ,   ')).toEqual([]);
  });
});

describe('parseCandidateBlocks', () => {
  it('splits blocks on blank lines and treats the first line as a name', () => {
    const raw = `Jane Doe
8 years Python, FastAPI

John Smith
5 years backend, AWS`;
    const blocks = parseCandidateBlocks(raw);
    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toMatchObject({
      candidate_id: 'cand-1',
      name: 'Jane Doe',
      cv_text: '8 years Python, FastAPI',
    });
    expect(blocks[1]).toMatchObject({
      candidate_id: 'cand-2',
      name: 'John Smith',
      cv_text: '5 years backend, AWS',
    });
  });

  it('tolerates whitespace-only lines between blocks', () => {
    const raw = `Alice
ML systems lead



Bob
backend engineer`;
    expect(parseCandidateBlocks(raw)).toHaveLength(2);
  });

  it('treats long or punctuated first lines as part of the CV body', () => {
    const raw = 'Hands-on engineer with 12 years of Python and distributed systems experience.';
    const blocks = parseCandidateBlocks(raw);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].name).toBeNull();
    expect(blocks[0].cv_text).toBe(raw);
  });

  it('returns an empty list for empty input', () => {
    expect(parseCandidateBlocks('')).toEqual([]);
    expect(parseCandidateBlocks('   \n  \n')).toEqual([]);
  });

  it('produces stable candidate_ids per index', () => {
    const blocks = parseCandidateBlocks('A\nfoo\n\nB\nbar\n\nC\nbaz');
    expect(blocks.map((b) => b.candidate_id)).toEqual(['cand-1', 'cand-2', 'cand-3']);
  });
});

describe('mergeCandidates (TASK-046 / FE-022)', () => {
  const c = (id: string, cv = `cv-${id}`): CandidateInput => ({
    candidate_id: id,
    cv_text: cv,
    name: null,
  });

  it('concatenates two non-overlapping lists preserving order', () => {
    expect(mergeCandidates([c('cand-1'), c('cand-2')], [c('upload-1')])).toMatchObject([
      { candidate_id: 'cand-1' },
      { candidate_id: 'cand-2' },
      { candidate_id: 'upload-1' },
    ]);
  });

  it('returns an empty list when both sources are empty', () => {
    expect(mergeCandidates([], [])).toEqual([]);
  });

  it('de-duplicates by candidate_id — manual paste wins over an earlier upload', () => {
    const fromText = [c('shared', 'from-text')];
    const fromUpload = [c('shared', 'from-upload'), c('upload-only')];
    const merged = mergeCandidates(fromText, fromUpload);
    expect(merged).toHaveLength(2);
    expect(merged[0]).toMatchObject({ candidate_id: 'shared', cv_text: 'from-text' });
    expect(merged[1]).toMatchObject({ candidate_id: 'upload-only' });
  });

  it('keeps the textarea blocks first then upload blocks (stable ordering for the user)', () => {
    const merged = mergeCandidates(
      [c('cand-1'), c('cand-2')],
      [c('upload-1'), c('upload-2'), c('upload-3')],
    );
    expect(merged.map((m) => m.candidate_id)).toEqual([
      'cand-1',
      'cand-2',
      'upload-1',
      'upload-2',
      'upload-3',
    ]);
  });
});
