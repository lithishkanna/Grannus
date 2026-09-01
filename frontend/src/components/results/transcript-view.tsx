'use client';
import { Badge } from '@/components/ui/badge';
import { Languages } from 'lucide-react';

export function TranscriptView({ 
  original, 
  english, 
  language 
}: { 
  original: string; 
  english: string; 
  language: string | null;
}) {
  return (
    <div className="bg-card rounded-2xl border border-border overflow-hidden shadow-sm">
      <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
        <h3 className="font-medium text-foreground flex items-center gap-2">
          <Languages className="w-4 h-4 text-primary" />
          Patient Transcript
        </h3>
        {language && (
          <Badge variant="secondary" className="font-normal capitalize bg-primary/10 text-primary hover:bg-primary/20">
            Detected: {language}
          </Badge>
        )}
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border">
        <div className="p-6">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Original Input</h4>
          <p className="text-foreground leading-relaxed font-serif text-lg">{original}</p>
        </div>
        <div className="p-6 bg-muted/5">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">English Translation</h4>
          <p className="text-foreground leading-relaxed text-lg">{english}</p>
        </div>
      </div>
    </div>
  );
}
