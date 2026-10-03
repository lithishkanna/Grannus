'use client';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { PriorityBadge } from '@/components/results/priority-badge';
import { AcousticBiomarkerCard } from '@/components/results/acoustic-biomarker-card';
import { VoiceReplyRecorder } from '@/components/dashboard/voice-reply-recorder';
import { FhirExportButton } from '@/components/dashboard/fhir-export-button';
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
  const patientLang = res.patient_input?.language || 'hi-IN';
  
  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto bg-card border-l border-border">
        <SheetHeader className="mb-6 mt-6">
          <SheetTitle className="font-heading text-xl">Consultation Details</SheetTitle>
        </SheetHeader>

        <div className="space-y-6">
          <div className="flex justify-between items-start flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <PriorityBadge level={res.priority?.level || 'UNKNOWN'} confidence={res.priority?.confidence} />
              {res.priority?.urgency_tier && (
                <span className={`px-2 py-0.5 rounded-full font-bold uppercase text-[10px] ${
                  res.priority.urgency_tier === 'emergency'
                    ? 'bg-destructive text-white'
                    : res.priority.urgency_tier === 'doctor_today'
                    ? 'bg-amber-500/20 text-amber-700 dark:text-amber-400 border border-amber-500/30'
                    : res.priority.urgency_tier === 'doctor_soon'
                    ? 'bg-blue-500/20 text-blue-700 dark:text-blue-400 border border-blue-500/30'
                    : 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30'
                }`}>
                  {res.priority.urgency_tier.replace('_', ' ')}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
              <Languages className="w-3 h-3" />
              {res.patient_input?.language || 'Unknown'}
            </div>
          </div>

          {/* Emergency Alert Banner if applicable */}
          {(res.priority?.urgency_tier === 'emergency' || res.priority?.emergency_override) && (
            <div className="p-3 bg-destructive/15 border border-destructive/30 rounded-xl text-destructive text-xs">
              <div className="font-bold flex items-center gap-1.5 mb-1">
                <span>⚠️ Emergency Referral — Call 108 / 112 Immediately</span>
              </div>
              <p className="text-[11px] text-foreground/80 mb-2">
                Critical symptoms detected. Immediate hospital or ambulance evaluation is required.
              </p>
              <div className="flex gap-2">
                <a href="tel:108" className="px-3 py-1 bg-destructive text-white rounded-md font-bold text-xs">
                  Call 108
                </a>
                <a href="tel:112" className="px-3 py-1 bg-secondary text-secondary-foreground border border-border rounded-md font-bold text-xs">
                  Call 112
                </a>
              </div>
            </div>
          )}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Chief Complaint</h3>
            <p className="text-base font-medium text-foreground">{res.clinical_summary?.chief_complaint || 'N/A'}</p>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Original Transcript</h3>
            <div className="p-3 bg-muted/30 rounded-lg border border-border text-xs italic text-foreground leading-relaxed">
              "{res.patient_input?.transcript_original}"
            </div>
          </div>

          {/* Active Symptoms */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center justify-between">
              <span>Reported Symptoms</span>
              <span className="text-[11px] font-normal text-muted-foreground">
                ({(res.clinical_summary?.symptoms?.filter((s: any) => !s.negated) || []).length})
              </span>
            </h3>
            {(() => {
              const activeSymptoms = res.clinical_summary?.symptoms?.filter((s: any) => !s.negated) || [];
              if (activeSymptoms.length === 0) {
                return <p className="text-xs text-muted-foreground italic">No active symptoms detected</p>;
              }
              return (
                <ul className="space-y-1.5">
                  {activeSymptoms.map((s: any, i: number) => (
                    <li key={i} className="flex items-center justify-between text-xs text-foreground bg-muted/20 px-3 py-1.5 rounded-lg border border-border/50">
                      <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                        <span className="font-medium capitalize">{s.name}</span>
                      </div>
                      {s.severity && (
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                          s.severity === 'severe' || s.severity === 'unbearable'
                            ? 'bg-destructive/15 text-destructive border border-destructive/20'
                            : s.severity === 'moderate'
                            ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/20'
                            : 'bg-primary/10 text-primary border border-primary/20'
                        }`}>
                          {s.severity}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              );
            })()}
          </div>

          {/* Pertinent Negatives / Denied Symptoms */}
          {(() => {
            const negatedSymptoms = res.clinical_summary?.symptoms?.filter((s: any) => s.negated) || [];
            if (negatedSymptoms.length === 0) return null;
            return (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                  Pertinent Negatives (Denied / Not Present)
                </h3>
                <ul className="space-y-1">
                  {negatedSymptoms.map((s: any, i: number) => (
                    <li key={i} className="flex items-center justify-between text-xs text-muted-foreground bg-muted/40 px-3 py-1 rounded-lg">
                      <span className="line-through">{s.name}</span>
                      <span className="text-[10px] font-medium bg-muted-foreground/15 px-2 py-0.5 rounded text-muted-foreground">
                        Denied
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })()}

          {/* Patient Background / Pre-existing Conditions */}
          {(res.clinical_summary?.existing_conditions?.length > 0 ||
            res.clinical_summary?.medications?.length > 0 ||
            res.clinical_summary?.allergies?.length > 0) && (
            <div className="pt-2 border-t border-border/60 space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Clinical Context</h3>
              {res.clinical_summary?.existing_conditions?.length > 0 && (
                <div className="text-xs">
                  <span className="font-semibold text-foreground">Conditions: </span>
                  <span className="text-muted-foreground">{res.clinical_summary.existing_conditions.join(', ')}</span>
                </div>
              )}
              {res.clinical_summary?.medications?.length > 0 && (
                <div className="text-xs">
                  <span className="font-semibold text-foreground">Medications: </span>
                  <span className="text-muted-foreground">{res.clinical_summary.medications.join(', ')}</span>
                </div>
              )}
              {res.clinical_summary?.allergies?.length > 0 && (
                <div className="text-xs">
                  <span className="font-semibold text-foreground">Allergies: </span>
                  <span className="text-muted-foreground">{res.clinical_summary.allergies.join(', ')}</span>
                </div>
              )}
            </div>
          )}

          {/* Acoustic Biomarkers if present */}
          {res.acoustic_biomarkers && (
            <AcousticBiomarkerCard data={res.acoustic_biomarkers} />
          )}

          {/* Voice Reply to Patient */}
          <VoiceReplyRecorder 
            patientLanguage={patientLang} 
            consultationId={consultation.id} 
          />

          {/* FHIR Export */}
          {res && <FhirExportButton result={res} />}
          
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
