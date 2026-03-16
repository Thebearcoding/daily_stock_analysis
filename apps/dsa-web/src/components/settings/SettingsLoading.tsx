import type React from 'react';

export const SettingsLoading: React.FC = () => {
  return (
    <div className="space-y-4 animate-fade-in">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="rounded-xl border border-warm-border bg-warm-surface/70 p-4">
          <div className="h-3 w-32 rounded bg-warm-surface-alt" />
          <div className="mt-3 h-10 rounded-lg bg-warm-bg" />
        </div>
      ))}
    </div>
  );
};
