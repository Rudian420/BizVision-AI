'use client';

import type { InputHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

type FormFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  /** Field-level error message (rendered under the input). */
  error?: string;
};

/** Labeled input with consistent dark-theme styling + error slot. */
export function FormField({ label, error, id, className, ...props }: FormFieldProps) {
  const fieldId = id ?? `field-${props.name ?? Math.random().toString(36).slice(2, 8)}`;
  return (
    <div className="mb-4">
      <label htmlFor={fieldId} className="mb-1 block font-ui text-xs uppercase tracking-wider text-text-secondary">
        {label}
      </label>
      <input
        id={fieldId}
        className={cn(
          'w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-ui text-sm text-text-primary outline-none transition focus:border-cyan focus:ring-1 focus:ring-cyan/40',
          error && 'border-coral focus:border-coral focus:ring-coral/40',
          className,
        )}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? `${fieldId}-error` : undefined}
        {...props}
      />
      {error && (
        <p id={`${fieldId}-error`} className="mt-1 font-ui text-xs text-coral">
          {error}
        </p>
      )}
    </div>
  );
}
