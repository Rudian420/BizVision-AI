import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge Tailwind classes with conflict resolution. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Format a 0–1 score as a percentage string. */
export function formatScore(score: number, digits = 0): string {
  return `${(score * 100).toFixed(digits)}%`;
}
