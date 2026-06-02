'use client';

/** Fullscreen fallback shown while the 3D canvas hydrates. */
export function LoadingScreen() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-void">
      <div className="flex flex-col items-center gap-4">
        <div className="h-12 w-12 animate-spin rounded-full border-2 border-electric/30 border-t-electric" />
        <p className="font-mono text-sm tracking-widest text-electric/80">
          INITIALISING NEURAL CORE…
        </p>
      </div>
    </div>
  );
}
