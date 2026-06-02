/**
 * Tests for the pure helpers exported by `CVUploadDropzone`
 * (TASK-046 / FE-022). The component's UI behaviour is exercised
 * by Playwright; here we lock the data-shaping invariants — the
 * boundary between the file picker and the `/upload-cvs` POST,
 * and between the parse result and the `/analyze` candidate body.
 */

import { describe, expect, it } from 'vitest';

import type { UploadFileResult } from '@/lib/recruitment/types';

import {
  filterAcceptedFiles,
  uploadResultToCandidate,
} from './CVUploadDropzone';

/** Mimic a browser `File` without pulling in `File` (jsdom has it
 * but we don't need its bytes). */
function fakeFile(name: string): File {
  return new File(['stub'], name, { type: 'application/octet-stream' });
}

describe('filterAcceptedFiles', () => {
  it('keeps PDF / DOCX / DOC / TXT files', () => {
    const files = [
      fakeFile('alice.pdf'),
      fakeFile('bob.docx'),
      fakeFile('carol.doc'),
      fakeFile('dan.txt'),
    ];
    expect(filterAcceptedFiles(files).map((f) => f.name)).toEqual([
      'alice.pdf',
      'bob.docx',
      'carol.doc',
      'dan.txt',
    ]);
  });

  it('matches case-insensitively (drag-drop from Windows / macOS often capitalises the ext)', () => {
    expect(filterAcceptedFiles([fakeFile('LOUD.PDF')]).map((f) => f.name)).toEqual([
      'LOUD.PDF',
    ]);
  });

  it('drops files with no extension or unsupported extensions', () => {
    expect(
      filterAcceptedFiles([
        fakeFile('README'),
        fakeFile('resume.zip'),
        fakeFile('photo.png'),
      ]),
    ).toEqual([]);
  });

  it('handles mixed batches without mutating the input', () => {
    const input = [
      fakeFile('a.pdf'),
      fakeFile('b.zip'),
      fakeFile('c.docx'),
      fakeFile('d.png'),
    ];
    const out = filterAcceptedFiles(input);
    expect(out.map((f) => f.name)).toEqual(['a.pdf', 'c.docx']);
    expect(input).toHaveLength(4); // unchanged
  });
});

describe('uploadResultToCandidate', () => {
  const baseResult = (over: Partial<UploadFileResult> = {}): UploadFileResult => ({
    file_id: '00000000-0000-0000-0000-000000000001',
    filename: 'alice.pdf',
    source: 'pdf',
    cv_text: 'Senior Python engineer with 8 years experience.',
    char_count: 47,
    skills: ['python'],
    years_experience: 8,
    education_level: 'master',
    error: null,
    ...over,
  });

  it('builds a CandidateInput with a 1-indexed synthetic id', () => {
    const cand = uploadResultToCandidate(baseResult(), 0);
    expect(cand).toEqual({
      candidate_id: 'upload-1',
      cv_text: 'Senior Python engineer with 8 years experience.',
      name: 'alice',
    });
  });

  it('strips the extension for the fallback name regardless of source', () => {
    expect(uploadResultToCandidate(baseResult({ filename: 'bob.docx' }), 1).name).toBe(
      'bob',
    );
    expect(
      uploadResultToCandidate(baseResult({ filename: 'carol_jane.txt' }), 4).name,
    ).toBe('carol_jane');
  });

  it('keeps a name with no extension untouched', () => {
    expect(uploadResultToCandidate(baseResult({ filename: 'NOEXT' }), 0).name).toBe(
      'NOEXT',
    );
  });

  it('does not include the parsed skills or years in the candidate body (they go to /analyze unchanged via cv_text)', () => {
    // Skills/years are useful for the user-facing list in the
    // dropzone, but the SBERT ranker reads cv_text — keep the
    // candidate body minimal so we don't double-count signals.
    const cand = uploadResultToCandidate(baseResult({ skills: ['python', 'docker'] }), 0);
    expect(cand).not.toHaveProperty('skills');
    expect(cand).not.toHaveProperty('years_experience');
  });
});
