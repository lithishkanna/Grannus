'use client';
import { useState } from 'react';
import { PriorityBadge } from '@/components/results/priority-badge';
import { AcousticBiomarkerCard } from '@/components/results/acoustic-biomarker-card';
import { VoiceReplyRecorder } from '@/components/dashboard/voice-reply-recorder';
import { FhirExportButton } from '@/components/dashboard/fhir-export-button';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  claimConsultationCase,
  releaseConsultationCase,
  reassignConsultationCase,
  overrideUrgencyTier,
} from '@/lib/api';
import {
  ShieldAlert,
  Lock,
  Unlock,
  UserCheck,
  Languages,
  AlertTriangle,
  ArrowRightLeft,
  Sliders,
  CheckCircle2,
  Clock,
  Sparkles,
  FileText,
  Volume2,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface CaseViewPanelProps {
  consultation: any;
  currentUser: any;
  onUpdate: () => void;
  doctorsRoster?: any[];
}

export function CaseViewPanel({
  consultation,
  currentUser,
  onUpdate,
  doctorsRoster = [],
}: CaseViewPanelProps) {
  const [isClaiming, setIsClaiming] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Reassign modal state
  const [showReassignModal, setShowReassignModal] = useState(false);
  const [targetDoctorId, setTargetDoctorId] = useState('');
  const [reassignReason, setReassignReason] = useState('');

  // Override tier modal state
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [newTier, setNewTier] = useState('doctor_today');
  const [overrideReason, setOverrideReason] = useState('');

  if (!consultation) {
    return (
      <div className="bg-card border border-border rounded-2xl p-12 text-center text-muted-foreground flex flex-col items-center justify-center min-h-[500px] shadow-sm">
        <FileText className="w-12 h-12 text-muted-foreground/30 mb-4" />
        <h3 className="font-heading text-lg font-medium text-foreground mb-1">No Case Selected</h3>
        <p className="text-sm text-muted-foreground max-w-sm">
          Select a consultation from the queue on the left to review symptoms, transcripts, and record a voice reply.
        </p>
      </div>
    );
  }

  const res = consultation.result || {};
  const patientLang = consultation.patient_language || res.patient_input?.language || 'ta-IN';
  const isEmergency = consultation.urgency_tier === 'emergency' || res.priority?.urgency_tier === 'emergency';
  const isClaimedByMe = consultation.is_claimed && (consultation.claimed_by_id === currentUser?.user_id || consultation.claimed_by_id === currentUser?.sub);
  const isClaimedByOther = consultation.is_claimed && !isClaimedByMe;

  const handleClaim = async () => {
    setIsClaiming(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const resp = await claimConsultationCase(consultation.id);
      setActionSuccess(resp.message || 'Case successfully claimed and locked.');
      onUpdate();
    } catch (err: any) {
      setActionError(err.message);
    } finally {
      setIsClaiming(false);
    }
  };

  const handleRelease = async () => {
    setIsClaiming(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const resp = await releaseConsultationCase(consultation.id);
      setActionSuccess(resp.message || 'Claim lock released.');
      onUpdate();
    } catch (err: any) {
      setActionError(err.message);
    } finally {
      setIsClaiming(false);
    }
  };

  const handleReassignSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetDoctorId || !reassignReason || reassignReason.trim().length < 5) {
      setActionError('Please select a doctor and provide a mandatory reason (min 5 characters).');
      return;
    }
    setActionError(null);
    try {
      await reassignConsultationCase(consultation.id, targetDoctorId, reassignReason);
      setShowReassignModal(false);
      setReassignReason('');
      setActionSuccess('Case successfully reassigned.');
      onUpdate();
    } catch (err: any) {
      setActionError(err.message);
    }
  };

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTier || !overrideReason || overrideReason.trim().length < 5) {
      setActionError('Please select a tier and provide a mandatory clinical reason (min 5 characters).');
      return;
    }
    setActionError(null);
    try {
      await overrideUrgencyTier(consultation.id, newTier, overrideReason);
      setShowOverrideModal(false);
      setOverrideReason('');
      setActionSuccess(`Urgency tier overridden to ${newTier.replace('_', ' ')}.`);
      onUpdate();
    } catch (err: any) {
      setActionError(err.message);
    }
  };

  return (
    <div className="bg-card border border-border rounded-2xl p-6 shadow-sm space-y-6 animate-gentle-fade-in">
      {/* Top Header & Urgency */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-border/60 pb-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`px-2.5 py-1 rounded-full font-bold uppercase text-xs tracking-wider ${
              consultation.urgency_tier === 'emergency'
                ? 'bg-destructive text-white'
                : consultation.urgency_tier === 'doctor_today'
                ? 'bg-amber-500/20 text-amber-700 dark:text-amber-400 border border-amber-500/30'
                : consultation.urgency_tier === 'doctor_soon'
                ? 'bg-blue-500/20 text-blue-700 dark:text-blue-400 border border-blue-500/30'
                : 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30'
            }`}>
              {consultation.urgency_tier ? consultation.urgency_tier.replace('_', ' ') : 'TIAGE'}
            </span>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {consultation.created_at ? formatDistanceToNow(new Date(consultation.created_at), { addSuffix: true }) : 'Just now'}
            </span>
            <span className="text-xs bg-muted/60 text-muted-foreground px-2 py-0.5 rounded flex items-center gap-1">
              <Languages className="w-3 h-3" /> {patientLang}
            </span>
          </div>
          <h2 className="text-xl font-heading font-medium text-foreground">
            {consultation.chief_complaint || res.clinical_summary?.chief_complaint || 'Patient Consultation'}
          </h2>
          {consultation.complaint_category && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Complaint Category: <span className="font-semibold text-foreground">{consultation.complaint_category.replace('_', ' ')}</span>
            </p>
          )}
        </div>

        {/* Claim status & Locking controls (B5.4) */}
        <div className="flex items-center gap-2">
          {isClaimedByOther ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border">
              <Lock className="w-3.5 h-3.5 text-amber-500" />
              Locked by {consultation.claimed_by_name || 'Another Doctor'}
            </span>
          ) : isClaimedByMe ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Claimed by You
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRelease}
                disabled={isClaiming}
                className="text-xs rounded-full h-8 gap-1"
              >
                <Unlock className="w-3 h-3" /> Release
              </Button>
            </div>
          ) : (
            <Button
              size="sm"
              onClick={handleClaim}
              disabled={isClaiming}
              className="gap-1.5 text-xs rounded-full h-8 bg-primary text-primary-foreground"
            >
              <Lock className="w-3 h-3" /> Claim Case
            </Button>
          )}
        </div>
      </div>

      {/* Action feedback */}
      {actionError && (
        <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-xl text-destructive text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}
      {actionSuccess && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-700 dark:text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Emergency alert card if emergency */}
      {isEmergency && (
        <div className="p-4 bg-destructive/15 border-2 border-destructive/40 rounded-xl text-destructive text-sm flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-bold">CRITICAL RED FLAG CASE (EMERGENCY)</h4>
            <p className="text-xs text-foreground/80 mt-1">
              Deterministic red flag triggered. Patient was prompted to call 108 / 112 immediately. ER alert logged.
            </p>
          </div>
        </div>
      )}

      {/* Dual Transcripts (F3.3) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-muted/30 border border-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Languages className="w-3.5 h-3.5" /> Regional Speech ({patientLang})
            </span>
          </div>
          <p className="text-sm italic text-foreground leading-relaxed">
            "{res.patient_input?.transcript_original || consultation.original_transcript || 'No original speech text available'}"
          </p>
        </div>

        <div className="bg-muted/30 border border-border rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-primary" /> English Translation (For Doctor)
            </span>
          </div>
          <p className="text-sm text-foreground leading-relaxed">
            "{res.patient_input?.transcript_english || consultation.english_transcript || 'No translated text available'}"
          </p>
        </div>
      </div>

      {/* Reported Symptoms & Pertinent Negatives */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Clinical Findings</h4>
        <div className="flex flex-wrap gap-2">
          {(res.clinical_summary?.symptoms?.filter((s: any) => !s.negated) || []).map((s: any, idx: number) => (
            <span
              key={idx}
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${
                s.severity === 'severe' || s.severity === 'unbearable'
                  ? 'bg-destructive/15 text-destructive border-destructive/30'
                  : 'bg-primary/10 text-primary border-primary/20'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              {s.name} {s.severity ? `(${s.severity})` : ''}
            </span>
          ))}

          {(res.clinical_summary?.symptoms?.filter((s: any) => s.negated) || []).map((s: any, idx: number) => (
            <span
              key={`neg-${idx}`}
              className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-muted/60 text-muted-foreground border border-border line-through"
            >
              {s.name} (Denied)
            </span>
          ))}
        </div>
      </div>

      {/* Patient Background / Context */}
      {(res.clinical_summary?.existing_conditions?.length > 0 ||
        res.clinical_summary?.medications?.length > 0 ||
        res.clinical_summary?.allergies?.length > 0) && (
        <div className="p-3 bg-muted/20 border border-border rounded-xl text-xs space-y-1">
          <span className="font-semibold text-foreground uppercase tracking-wider text-[10px]">Patient Context:</span>
          {res.clinical_summary?.existing_conditions?.length > 0 && (
            <div><span className="text-muted-foreground">Conditions:</span> {res.clinical_summary.existing_conditions.join(', ')}</div>
          )}
          {res.clinical_summary?.medications?.length > 0 && (
            <div><span className="text-muted-foreground">Medications:</span> {res.clinical_summary.medications.join(', ')}</div>
          )}
          {res.clinical_summary?.allergies?.length > 0 && (
            <div><span className="text-muted-foreground">Allergies:</span> {res.clinical_summary.allergies.join(', ')}</div>
          )}
        </div>
      )}

      {/* Acoustic Biomarkers (Advisory only) */}
      {res.acoustic_biomarkers && (
        <div className="pt-2">
          <AcousticBiomarkerCard data={res.acoustic_biomarkers} />
        </div>
      )}

      {/* Doctor Action Controls: Re-route, Override Tier, Request More Info (F3.5) */}
      <div className="pt-4 border-t border-border flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowReassignModal(true)}
          className="text-xs rounded-full gap-1.5"
        >
          <ArrowRightLeft className="w-3.5 h-3.5" /> Re-route / Reassign
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowOverrideModal(true)}
          className="text-xs rounded-full gap-1.5"
        >
          <Sliders className="w-3.5 h-3.5" /> Override Urgency Tier
        </Button>

        {res && <FhirExportButton result={res} />}
      </div>

      {/* Reassign Modal */}
      {showReassignModal && (
        <div className="p-4 bg-muted/40 border border-border rounded-xl space-y-3">
          <h4 className="text-xs font-bold text-foreground">Reassign Case (B5.6)</h4>
          <select
            value={targetDoctorId}
            onChange={(e) => setTargetDoctorId(e.target.value)}
            className="w-full bg-card border border-border rounded-lg p-2 text-xs text-foreground"
          >
            <option value="">Select target clinician...</option>
            {doctorsRoster.map((doc) => (
              <option key={doc.id || doc.email} value={doc.id || doc.email}>
                {doc.full_name} ({doc.specialty || doc.department_code}) - {doc.languages?.join(', ')}
              </option>
            ))}
          </select>
          <Input
            placeholder="Mandatory clinical rationale for reassignment..."
            value={reassignReason}
            onChange={(e) => setReassignReason(e.target.value)}
            className="text-xs bg-card"
          />
          <div className="flex gap-2 justify-end">
            <Button size="sm" variant="ghost" onClick={() => setShowReassignModal(false)} className="text-xs">
              Cancel
            </Button>
            <Button size="sm" onClick={handleReassignSubmit} className="text-xs bg-primary text-primary-foreground">
              Confirm Reassignment
            </Button>
          </div>
        </div>
      )}

      {/* Override Tier Modal */}
      {showOverrideModal && (
        <div className="p-4 bg-muted/40 border border-border rounded-xl space-y-3">
          <h4 className="text-xs font-bold text-foreground">Clinical Override of Urgency Tier (B5.6)</h4>
          <select
            value={newTier}
            onChange={(e) => setNewTier(e.target.value)}
            className="w-full bg-card border border-border rounded-lg p-2 text-xs text-foreground"
          >
            <option value="emergency">Emergency (Immediate ER alert)</option>
            <option value="doctor_today">Doctor Today (Within 24 hours)</option>
            <option value="doctor_soon">Doctor Soon (Within 2-3 days)</option>
            <option value="self_care">Self-Care (Mild, self-limiting)</option>
          </select>
          <Input
            placeholder="Mandatory clinical justification for overriding tier..."
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            className="text-xs bg-card"
          />
          <div className="flex gap-2 justify-end">
            <Button size="sm" variant="ghost" onClick={() => setShowOverrideModal(false)} className="text-xs">
              Cancel
            </Button>
            <Button size="sm" onClick={handleOverrideSubmit} className="text-xs bg-primary text-primary-foreground">
              Submit Override
            </Button>
          </div>
        </div>
      )}

      {/* Voice Reply Recorder (F3.4) */}
      <div className="pt-2">
        <VoiceReplyRecorder
          patientLanguage={patientLang}
          consultationId={consultation.id}
        />
      </div>
    </div>
  );
}
