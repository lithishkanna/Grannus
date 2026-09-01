'use client';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { PriorityBadge } from '@/components/results/priority-badge';
import { ArrowRight, Languages } from 'lucide-react';
import { useRouter } from 'next/navigation';

export function DetailDrawer({ 
  consultation, 
  isOpen, 
  onClose 
}: { 
  consultation: any | null; 
  isOpen: boolean; 
  onClose: () => void 
}) {
  const router = useRouter();
  if (!consultation) return null;

  const res = consultation.result;
  
  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto bg-card border-l border-border">
        <SheetHeader className="mb-6 mt-6">
          <SheetTitle className="font-heading text-xl">Consultation Details</SheetTitle>
        </SheetHeader>

        <div className="space-y-6">
          <div className="flex justify-between items-start">
            <PriorityBadge level={res.priority?.level || 'UNKNOWN'} confidence={res.priority?.confidence} />
            <div className="flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
              <Languages className="w-3 h-3" />
              {res.patient_input?.language || 'Unknown'}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-1">Chief Complaint</h3>
            <p className="text-lg font-medium text-foreground">{res.clinical_summary?.chief_complaint || 'N/A'}</p>
          </div>

          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">Original Transcript</h3>
            <div className="p-3 bg-muted/30 rounded-lg border border-border text-sm italic text-foreground">
              "{res.patient_input?.transcript_original}"
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">Symptoms</h3>
            <ul className="space-y-1">
              {res.clinical_summary?.symptoms?.map((s: any, i: number) => (
                <li key={i} className="flex items-center gap-2 text-sm text-foreground">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                  {s.name} {s.severity && <span className="text-xs text-muted-foreground">({s.severity})</span>}
                </li>
              ))}
            </ul>
          </div>
          
          <Button 
            className="w-full rounded-full gap-2 mt-4 bg-primary text-primary-foreground hover:bg-primary/90"
            onClick={() => router.push(`/results?id=${consultation.id}`)}
          >
            View Full Report <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
