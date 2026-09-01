'use client';

export function Footer() {
  return (
    <footer className="w-full border-t border-border bg-background py-8">
      <div className="container mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex flex-col gap-1 text-center md:text-left">
          <span className="font-heading text-lg font-medium text-foreground">Grannus — RuralCare AI</span>
          <span className="text-sm text-muted-foreground">Bridging the healthcare & language gap</span>
        </div>
        <div className="text-xs text-muted-foreground/70 max-w-md text-center md:text-right">
          Disclaimer: This system uses AI for preliminary symptom assessment and translation. It does not replace professional medical advice. Always consult a qualified healthcare provider.
        </div>
      </div>
    </footer>
  );
}
