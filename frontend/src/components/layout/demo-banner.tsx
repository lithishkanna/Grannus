import React from 'react';
import { AlertTriangle } from 'lucide-react';

export function DemoBanner() {
  return (
    <aside
      aria-label="Clinical safety warning"
      className="bg-amber-500 text-amber-950 font-medium text-xs sm:text-sm py-2 px-4 text-center flex items-center justify-center gap-2 border-b border-amber-600/30 shadow-sm z-50 sticky top-0"
    >
      <AlertTriangle className="w-4 h-4 text-amber-900 shrink-0" />
      <span>
        <strong>Demo: synthetic data, not medical advice.</strong> Telemedicine urgency routing prototype. In a medical emergency, call 108 or 112 immediately.
      </span>
    </aside>
  );
}
