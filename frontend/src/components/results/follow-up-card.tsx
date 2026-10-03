'use client';

import React, { useState } from 'react';
import { Calendar, AlertCircle, ArrowUpRight, CheckCircle2, RefreshCw, PhoneCall } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { UrgencyTier, checkInConsultation, escalateConsultation, CheckInResponse } from '@/lib/api';

interface FollowUpCardProps {
  consultationId: string;
  initialTier?: UrgencyTier;
  followUpDays?: number;
}

export function FollowUpCard({
  consultationId,
  initialTier = 'self_care',
  followUpDays = 2,
}: FollowUpCardProps) {
  const [tier, setTier] = useState<UrgencyTier>(initialTier);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [checkInResult, setCheckInResult] = useState<CheckInResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCheckIn = async (status: 'improving' | 'same' | 'worse') => {
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await checkInConsultation(consultationId, status);
      setCheckInResult(res);
      setTier(res.new_tier);
    } catch (err: any) {
      console.error('Check-in failed:', err);
      setError('Could not record check-in. Please ensure you are connected or visit the nearest clinic.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOneTapEscalate = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await escalateConsultation(consultationId, "Patient tapped 'I Feel Worse' emergency escalation");
      setCheckInResult(res);
      setTier(res.new_tier);
    } catch (err: any) {
      console.error('Escalation failed:', err);
      setError('Could not record escalation. If your condition is severe, please call 108 or 112 immediately.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const tierColors: Record<UrgencyTier, { bg: string; text: string; label: string }> = {
    emergency: { bg: 'bg-destructive/15 border-destructive', text: 'text-destructive', label: 'Emergency Referral (Immediate 108/112)' },
    doctor_today: { bg: 'bg-amber-500/15 border-amber-500', text: 'text-amber-600 dark:text-amber-400', label: 'Doctor Visit Today (Within 24 Hours)' },
    doctor_soon: { bg: 'bg-blue-500/15 border-blue-500', text: 'text-blue-600 dark:text-blue-400', label: 'Doctor Visit Soon (Next 48–72 Hours)' },
    self_care: { bg: 'bg-emerald-500/15 border-emerald-500', text: 'text-emerald-600 dark:text-emerald-400', label: 'Self-Care & Home Monitoring' },
  };

  const currentConfig = tierColors[tier] || tierColors.self_care;

  return (
    <div className={`p-6 rounded-2xl border-2 ${currentConfig.bg} shadow-sm transition-all`}>
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-border/50">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Calendar className="w-5 h-5 text-primary" />
            <h3 className="font-heading font-semibold text-lg text-foreground">
              Follow-Up & Clinical Escalation Loop
            </h3>
          </div>
          <p className="text-xs text-muted-foreground">
            Recommended follow-up in <span className="font-semibold text-foreground">{followUpDays} days</span>. Check in below or tap if symptoms worsen.
          </p>
        </div>

        <div className={`px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider border ${currentConfig.text} ${currentConfig.bg}`}>
          Current Tier: {currentConfig.label}
        </div>
      </div>

      {/* Escalation alert feedback if present */}
      {checkInResult && (
        <div className={`my-4 p-4 rounded-xl border ${checkInResult.is_escalated ? 'bg-destructive/10 border-destructive/30 text-destructive' : 'bg-primary/10 border-primary/20 text-foreground'}`}>
          <div className="flex items-start gap-3">
            {checkInResult.is_escalated ? (
              <AlertCircle className="w-5 h-5 shrink-0 text-destructive mt-0.5" />
            ) : (
              <CheckCircle2 className="w-5 h-5 shrink-0 text-primary mt-0.5" />
            )}
            <div>
              <p className="text-sm font-semibold">
                {checkInResult.is_escalated ? 'Clinical Urgency Escalated!' : 'Follow-up Status Recorded'}
              </p>
              <p className="text-xs mt-1 text-foreground/85">
                {checkInResult.message}
              </p>
              {checkInResult.new_tier === 'emergency' && (
                <div className="mt-3 flex items-center gap-2">
                  <a
                    href="tel:108"
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-destructive text-white text-xs font-bold shadow hover:bg-destructive/90"
                  >
                    <PhoneCall className="w-3.5 h-3.5" /> Call 108 Ambulance
                  </a>
                  <a
                    href="tel:112"
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-secondary text-secondary-foreground text-xs font-bold border border-border"
                  >
                    <PhoneCall className="w-3.5 h-3.5" /> Call 112
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="my-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs">
          {error}
        </div>
      )}

      {/* Action Buttons */}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium text-muted-foreground mr-1">Check-in:</span>
        <Button
          variant="outline"
          size="sm"
          disabled={isSubmitting}
          onClick={() => handleCheckIn('improving')}
          className="rounded-xl border-emerald-500/40 hover:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 gap-1.5 text-xs"
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          Improving
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={isSubmitting}
          onClick={() => handleCheckIn('same')}
          className="rounded-xl border-blue-500/40 hover:bg-blue-500/10 text-blue-700 dark:text-blue-400 gap-1.5 text-xs"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          About the Same
        </Button>

        {/* Dedicated One-Tap "I Feel Worse" Escalation Button */}
        <Button
          size="sm"
          disabled={isSubmitting}
          onClick={handleOneTapEscalate}
          className="rounded-xl bg-destructive hover:bg-destructive/90 text-white font-bold gap-2 text-xs shadow-md ml-auto"
        >
          <AlertCircle className="w-4 h-4 animate-pulse" />
          ⚠️ I Feel Worse (Escalate Urgency)
        </Button>
      </div>
    </div>
  );
}
