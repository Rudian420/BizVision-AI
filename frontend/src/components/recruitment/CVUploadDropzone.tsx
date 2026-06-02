'use client';

import { useCallback, useRef, useState, type DragEvent } from 'react';

import { uploadCVs } from '@/lib/recruitment/client';
import type { UploadFileResult } from '@/lib/recruitment/types';

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt'] as const;
const MAX_FILES = 50; // matches the backend's per-batch cap (TASK-045)

type CVUploadDropzoneProps = {
  /** Called with the per-file parse results once an upload batch
   * completes. Files that failed to parse appear with a non-null
   * `error` — callers usually filter them out before piping into
   * `/analyze`. */
  onParsed: (results: UploadFileResult[]) => void;
  /** Visible per-file count already merged into the candidate list,
   * for the helper banner ("3 CVs parsed and added"). */
  alreadyAdded?: number;
};

/**
 * Drag-drop + click-to-browse zone that POSTs PDFs / DOCX / TXTs to
 * `POST /api/v1/recruitment/upload-cvs` and surfaces the per-file
 * parse results (cv_text length, skills found, years of experience,
 * education, or an error for malformed files). FE-022 / TASK-046.
 *
 * Stateless beyond the in-flight upload — once the parsed results are
 * handed to `onParsed`, the parent owns the candidate list and the
 * dropzone resets to an empty drop state for the next batch. This
 * lets the user upload multiple batches without manually clearing
 * anything.
 */
export function CVUploadDropzone({ onParsed, alreadyAdded = 0 }: CVUploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [hover, setHover] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastBatch, setLastBatch] = useState<UploadFileResult[]>([]);

  const submitFiles = useCallback(
    async (files: File[]) => {
      setError(null);
      const accepted = filterAcceptedFiles(files);
      if (accepted.length === 0) {
        setError('No supported files in selection. Accepted: PDF, DOCX, DOC, TXT.');
        return;
      }
      if (accepted.length > MAX_FILES) {
        setError(`Maximum ${MAX_FILES} files per batch.`);
        return;
      }
      setUploading(true);
      try {
        const resp = await uploadCVs(accepted);
        setLastBatch(resp.uploaded);
        onParsed(resp.uploaded);
      } catch (e) {
        setError(toErrorMessage(e));
      } finally {
        setUploading(false);
      }
    },
    [onParsed],
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setHover(false);
      const files = Array.from(e.dataTransfer.files ?? []);
      void submitFiles(files);
    },
    [submitFiles],
  );

  const onDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setHover(true);
  }, []);

  const onDragLeave = useCallback(() => setHover(false), []);

  const openPicker = useCallback(() => inputRef.current?.click(), []);

  return (
    <section
      aria-label="Upload CV files"
      className="space-y-3 rounded-xl border border-white/10 bg-white/[0.02] p-4"
    >
      <header className="flex items-baseline justify-between gap-2">
        <span className="font-ui text-xs uppercase tracking-widest text-text-secondary">
          Or upload CVs
        </span>
        <span className="font-data text-[11px] text-text-secondary">
          PDF · DOCX · TXT · max {MAX_FILES} per batch
        </span>
      </header>

      <div
        role="button"
        tabIndex={0}
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openPicker();
          }
        }}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        aria-disabled={uploading}
        className={[
          'cursor-pointer rounded-lg border-2 border-dashed px-4 py-6 text-center font-ui text-sm transition',
          uploading
            ? 'cursor-not-allowed border-cyan/40 bg-cyan/5 text-text-secondary'
            : hover
              ? 'border-cyan/80 bg-cyan/10 text-text-primary'
              : 'border-white/20 bg-white/[0.01] text-text-secondary hover:border-cyan/60',
        ].join(' ')}
      >
        {uploading ? (
          <>Parsing CVs through pypdf / python-docx + EntityExtractor…</>
        ) : (
          <>
            <span className="text-text-primary">Drop CVs here</span>{' '}
            <span className="text-text-secondary/80">or click to browse.</span>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          name="cv_files"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          multiple
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            // Reset input so re-uploading the same file fires onChange.
            if (inputRef.current) inputRef.current.value = '';
            void submitFiles(files);
          }}
        />
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-xs text-coral"
        >
          {error}
        </p>
      )}

      {alreadyAdded > 0 && (
        <p className="font-ui text-xs text-emerald">
          {alreadyAdded} parsed CV{alreadyAdded === 1 ? '' : 's'} merged into the
          candidate list below.
        </p>
      )}

      {lastBatch.length > 0 && (
        <ul aria-label="Parse results" className="space-y-1.5">
          {lastBatch.map((file) => (
            <li
              key={file.file_id}
              className="flex items-baseline justify-between gap-2 rounded border border-white/[0.06] bg-white/[0.02] px-3 py-2 font-ui text-xs"
            >
              <span className="truncate text-text-primary" title={file.filename}>
                {file.filename}
              </span>
              <span className="shrink-0 font-data text-[11px]">
                {file.error ? (
                  <span className="text-coral">{file.error}</span>
                ) : (
                  <span className="text-text-secondary">
                    {file.char_count} chars
                    {file.years_experience !== null && (
                      <> · {file.years_experience} yrs</>
                    )}
                    {file.skills.length > 0 && <> · {file.skills.length} skills</>}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ── Helpers — pure, testable ───────────────────────────────────────

/** Keep only files whose extension is in the accept list. We
 * deliberately re-filter client-side instead of trusting the
 * `<input accept>` attribute — drag-drop bypasses it on many
 * browsers. */
export function filterAcceptedFiles(files: File[]): File[] {
  return files.filter((f) => {
    const dot = f.name.lastIndexOf('.');
    if (dot < 0) return false;
    const ext = f.name.slice(dot).toLowerCase();
    return (ACCEPTED_EXTENSIONS as readonly string[]).includes(ext);
  });
}

/** Convert a parsed `UploadFileResult` into the wire shape consumed
 * by `/recruitment/analyze` (`CandidateInput`). Files that didn't
 * parse are filtered upstream — pre-call this only on results whose
 * `error` is null. */
export function uploadResultToCandidate(
  file: UploadFileResult,
  idx: number,
): { candidate_id: string; cv_text: string; name: string | null } {
  // Strip extension for a slightly nicer fallback name.
  const dot = file.filename.lastIndexOf('.');
  const baseName = dot > 0 ? file.filename.slice(0, dot) : file.filename;
  return {
    candidate_id: `upload-${idx + 1}`,
    cv_text: file.cv_text,
    name: baseName,
  };
}

function toErrorMessage(e: unknown): string {
  if (e && typeof e === 'object' && 'message' in e) {
    return String((e as { message: unknown }).message);
  }
  return 'Upload failed. Please try again.';
}
