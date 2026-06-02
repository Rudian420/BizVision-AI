'use client';

import type { TextareaHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

type TextAreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  error?: string;
  /** Optional caption underneath the label (e.g. word count hint). */
  hint?: string;
};

/** Labeled textarea matching the auth FormField look-and-feel. */
export function TextArea({ label, error, hint, id, className, ...props }: TextAreaProps) {
  const fieldId = id ?? `ta-${props.name ?? Math.random().toString(36).slice(2, 8)}`;
  return (
    <div className="mb-4">
      <label
        htmlFor={fieldId}
        className="mb-1 flex items-center justify-between font-ui text-xs uppercase tracking-wider text-text-secondary"
      >
        <span>{label}</span>
        {hint && <span className="font-ui text-[10px] normal-case text-text-secondary/70">{hint}</span>}
      </label>
      <textarea
        id={fieldId}
        className={cn(
          'w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-ui text-sm text-text-primary outline-none transition focus:border-cyan focus:ring-1 focus:ring-cyan/40',
          error && 'border-coral focus:border-coral focus:ring-coral/40',
          className,
        )}
        aria-invalid={error ? 'true' : undefined}
        {...props}
      />
      {error && (
        <p className="mt-1 font-ui text-xs text-coral">{error}</p>
      )}
    </div>
  );
}
