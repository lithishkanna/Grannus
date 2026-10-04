'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Calendar,
  Clock,
  User,
  ArrowRight,
  ShieldAlert,
  AlertTriangle,
  Stethoscope,
  HeartPulse,
  Volume2,
  FileText,
  Plus,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  getActiveProfile,
  getPatientProfiles,
  PatientProfile,
  UrgencyTier,
} from '@/lib/api';
import { formatDistanceToNow } from 'date-fns';

export default function HistoryPage() {
  const router = useRouter();
  const [activeProfile, setActiveProfile] = useState<PatientProfile | null>(null);
  const [profiles, setProfiles] = useState<PatientProfile[]>([]);
  const [consultations, setConsultations] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const prof = getActiveProfile();
    setActiveProfile(prof);

    // Load available family profiles
    getPatientProfiles()
      .then((data) => setProfiles(Array.isArray(data) ? data : []))
      .catch((err) => console.warn('Could not load profiles', err));

    // Load consultations for profile
    const token = typeof window !== 'undefined' ? localStorage.getItem('grannus_auth_token') : null;
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    if (token) {
      fetch(`${baseUrl}/api/v1/patient/consultations${prof?.id ? `?profile_id=${prof.id}` : ''}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => (res.ok ? res.json() : { consultations: [] }))
        .then((data) => setConsultations(data.consultations || []))
        .catch((err) => console.warn('Could not fetch history:', err))
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const tierStyles: Record<string, { bg: string; text: string; label: string; icon: any }> = {
    emergency: {
      bg: 'bg-destructive/15 border-destructive/30',
      text: 'text-destructive',
      label: 'Emergency (108/112)',
      icon: ShieldAlert,
    },
    doctor_today: {
      bg: 'bg-amber-500/15 border-amber-500/30',
      text: 'text-amber-700 dark:text-amber-400',
      label: 'Doctor Today (24h)',
      icon: AlertTriangle,
    },
    doctor_soon: {
      bg: 'bg-blue-500/15 border-blue-500/30',
      text: 'text-blue-700 dark:text-blue-400',
      label: 'Doctor Soon (48-72h)',
      icon: Stethoscope,
    },
    self_care: {
      bg: 'bg-emerald-500/15 border-emerald-500/30',
      text: 'text-emerald-700 dark:text-emerald-400',
      label: 'Self-Care & Home Monitoring',
      icon: HeartPulse,
    },
  };

  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl animate-gentle-fade-in">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 pb-4 border-b border-border">
        <div>
          <h1 className="text-3xl font-heading font-semibold text-foreground">
            Consultation History
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Timeline of past voice intakes, urgency tiers, and doctor replies per patient profile.
          </p>
        </div>

        <Button onClick={() => router.push('/input')} className="gap-2 rounded-full self-start md:self-auto">
          <Plus className="w-4 h-4" /> New Voice Intake
        </Button>
      </div>

      {/* Profile Header & Switcher */}
      {activeProfile && (
        <div className="bg-card border border-border rounded-2xl p-4 sm:p-5 mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-primary text-primary-foreground font-bold text-lg flex items-center justify-center">
              {activeProfile.full_name.charAt(0).toUpperCase()}
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-primary tracking-wider">
                Active Patient Profile
              </span>
              <h3 className="text-base font-semibold text-foreground">
                {activeProfile.full_name}{' '}
                <span className="text-xs font-normal text-muted-foreground">
                  ({activeProfile.relation}, {activeProfile.age || 'Unknown'} yrs)
                </span>
              </h3>
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push('/login')}
            className="text-xs rounded-xl"
          >
            Switch Profile
          </Button>
        </div>
      )}

      {/* History Timeline */}
      {isLoading ? (
        <div className="p-12 text-center text-muted-foreground animate-pulse">
          Loading consultation records...
        </div>
      ) : consultations.length === 0 ? (
        <div className="bg-card border border-border rounded-2xl p-12 text-center shadow-sm">
          <FileText className="w-12 h-12 text-muted-foreground/40 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-foreground">No Consultations Yet</h3>
          <p className="text-xs text-muted-foreground max-w-sm mx-auto mt-1 mb-6">
            You haven't recorded any voice consultations for this profile yet. Start by recording your symptoms.
          </p>
          <Button onClick={() => router.push('/input')} className="gap-2 rounded-full px-6">
            <Plus className="w-4 h-4" /> Record First Intake
          </Button>
        </div>
      ) : (
        <div className="relative pl-6 border-l-2 border-border space-y-8">
          {consultations.map((item, index) => {
            const tierKey = item.urgency_tier || 'self_care';
            const tierCfg = tierStyles[tierKey] || tierStyles.self_care;
            const TierIcon = tierCfg.icon;

            return (
              <div key={item.id || index} className="relative group">
                {/* Timeline node icon */}
                <div className="absolute -left-[35px] top-1.5 w-6 h-6 rounded-full bg-background border-2 border-primary flex items-center justify-center text-primary shadow-sm">
                  <span className="w-2 h-2 rounded-full bg-primary" />
                </div>

                <div className="bg-card border border-border rounded-2xl p-5 shadow-sm transition-all hover:border-primary/40">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-3 pb-3 border-b border-border/40">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider border ${tierCfg.bg} ${tierCfg.text}`}
                      >
                        <TierIcon className="w-3 h-3" />
                        {tierCfg.label}
                      </span>
                      {item.complaint_category && (
                        <span className="text-[11px] text-muted-foreground capitalize">
                          • {item.complaint_category.replace('_', ' ')}
                        </span>
                      )}
                    </div>

                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {item.created_at
                        ? formatDistanceToNow(new Date(item.created_at), { addSuffix: true })
                        : 'Recent'}
                    </span>
                  </div>

                  <h4 className="text-base font-semibold text-foreground mb-2">
                    {item.chief_complaint || 'Voice Consultation'}
                  </h4>

                  <p className="text-xs text-muted-foreground line-clamp-2 mb-4 italic">
                    "{item.original_transcript || item.english_transcript || 'Recorded voice consultation'}"
                  </p>

                  <div className="flex items-center justify-between pt-2">
                    <span className="text-xs text-muted-foreground">
                      Language: {item.patient_language || 'Native'}
                    </span>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => router.push(`/results?id=${item.id}`)}
                      className="gap-1.5 rounded-full text-xs"
                    >
                      <span>View Result & Audio</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
