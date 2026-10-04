'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useConsultations } from '@/hooks/use-consultations';
import { StatsOverview } from '@/components/dashboard/stats-overview';
import { PriorityFilter } from '@/components/dashboard/priority-filter';
import { CaseViewPanel } from '@/components/dashboard/case-view-panel';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toggleDoctorAvailability, getDoctorRoster } from '@/lib/api';
import {
  Search,
  Plus,
  ShieldCheck,
  LogIn,
  LogOut,
  Clock,
  Lock,
  CheckCircle2,
  AlertCircle,
  Radio,
  UserCheck,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export default function DashboardPage() {
  const router = useRouter();
  const {
    consultations,
    isLoading,
    error,
    filterByPriority,
    setFilterByPriority,
    searchQuery,
    setSearchQuery,
    refetch,
  } = useConsultations();

  const [selectedConsultation, setSelectedConsultation] = useState<any | null>(null);
  const [currentUser, setCurrentUser] = useState<any | null>(null);
  const [isOnDuty, setIsOnDuty] = useState<boolean>(true);
  const [doctorsRoster, setDoctorsRoster] = useState<any[]>([]);

  useEffect(() => {
    try {
      const token = localStorage.getItem('grannus_auth_token');
      const stored = localStorage.getItem('grannus_user');
      if (!token || !stored) {
        router.push('/login?redirect=/dashboard');
        return;
      }
      const u = JSON.parse(stored);
      // F1.5 Role guard: Doctor dashboard restricted to doctors, nurses, and admins
      if (u.role === 'patient') {
        router.push('/input');
        return;
      }
      setCurrentUser(u);
      if (typeof u.is_on_duty === 'boolean') {
        setIsOnDuty(u.is_on_duty);
      }
    } catch (e) {
      console.error('Failed to load user session', e);
      router.push('/login');
      return;
    }

    // Load doctor roster for reassignment
    getDoctorRoster()
      .then((res) => {
        if (res && res.doctors) setDoctorsRoster(res.doctors);
      })
      .catch((e) => console.warn('Could not load roster', e));
  }, []);

  // Sync selected consultation with fresh list
  useEffect(() => {
    if (consultations.length > 0) {
      if (!selectedConsultation) {
        setSelectedConsultation(consultations[0]);
      } else {
        const updated = consultations.find((c) => c.id === selectedConsultation.id);
        if (updated) setSelectedConsultation(updated);
      }
    }
  }, [consultations]);

  const handleLogout = () => {
    localStorage.removeItem('grannus_auth_token');
    localStorage.removeItem('grannus_user');
    setCurrentUser(null);
    router.push('/login');
  };

  const handleToggleDuty = async () => {
    const nextState = !isOnDuty;
    setIsOnDuty(nextState);
    try {
      await toggleDoctorAvailability(nextState);
      if (currentUser) {
        const updated = { ...currentUser, is_on_duty: nextState };
        localStorage.setItem('grannus_user', JSON.stringify(updated));
        setCurrentUser(updated);
      }
    } catch (err) {
      console.error('Failed to toggle duty', err);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-12 flex flex-col items-center justify-center min-h-[60vh]">
        <div className="w-10 h-10 border-4 border-primary/30 border-t-primary rounded-full animate-spin mb-4" />
        <p className="text-muted-foreground">Loading doctor dashboard & queue...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-12 text-center text-red-500">
        Error loading queue: {error}
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-gentle-fade-in">
      {/* Top Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4 pb-4 border-b border-border">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl md:text-3xl font-heading font-medium text-foreground">
              Doctor Consultation Queue
            </h1>
            {currentUser?.is_verified_doctor ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
                <ShieldCheck className="w-3.5 h-3.5" />
                Verified RMP: {currentUser.doctor_registration_number}
              </span>
            ) : null}
          </div>
          <p className="text-muted-foreground text-xs md:text-sm mt-1">
            Urgent-first triage queue with complaint category routing and claim locking.
          </p>
        </div>

        {/* Actions & Availability Toggle (F3.6) */}
        <div className="flex items-center gap-3 flex-wrap">
          {currentUser && currentUser.role === 'doctor' && (
            <button
              onClick={handleToggleDuty}
              className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-all ${
                isOnDuty
                  ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                  : 'bg-muted text-muted-foreground border-border'
              }`}
            >
              <Radio className={`w-3.5 h-3.5 ${isOnDuty ? 'animate-pulse text-emerald-500' : 'text-muted-foreground'}`} />
              {isOnDuty ? 'ON DUTY' : 'OFF DUTY'}
            </button>
          )}

          {currentUser ? (
            <Button variant="outline" size="sm" onClick={handleLogout} className="gap-1.5 rounded-full text-xs">
              <LogOut className="w-3.5 h-3.5" /> Sign Out
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={() => router.push('/login')} className="gap-1.5 rounded-full text-xs">
              <LogIn className="w-3.5 h-3.5" /> Clinician Login
            </Button>
          )}

          <Button onClick={() => router.push('/input')} className="gap-2 rounded-full px-5 text-xs">
            <Plus className="w-4 h-4" /> New Intake
          </Button>
        </div>
      </div>

      <StatsOverview consultations={consultations} />

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 my-6">
        <PriorityFilter selected={filterByPriority} onChange={setFilterByPriority} />

        <div className="relative w-full md:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search symptoms, language, complaint..."
            className="pl-9 rounded-full bg-card text-xs"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* F3.1 Split View: Queue List on Left (col-span-5), Selected Case on Right (col-span-7) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Pane: Queue List (F3.2) */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Queue ({consultations.length})
            </span>
            <span className="text-xs text-muted-foreground">Sorted: Urgent First</span>
          </div>

          {consultations.length === 0 ? (
            <div className="bg-card border border-border rounded-xl p-8 text-center text-muted-foreground text-xs">
              No consultations found matching your filters.
            </div>
          ) : (
            <div className="space-y-2 max-h-[750px] overflow-y-auto pr-1">
              {consultations.map((c) => {
                const isSelected = selectedConsultation?.id === c.id;
                const tier = c.urgency_tier || c.result?.priority?.urgency_tier || 'doctor_soon';
                const isEmergency = tier === 'emergency';

                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedConsultation(c)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer text-left ${
                      isSelected
                        ? 'bg-primary/5 border-primary shadow-sm'
                        : 'bg-card border-border hover:border-primary/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className={`px-2 py-0.5 rounded-full font-bold uppercase text-[9px] ${
                          tier === 'emergency'
                            ? 'bg-destructive text-white'
                            : tier === 'doctor_today'
                            ? 'bg-amber-500/20 text-amber-700 dark:text-amber-400 border border-amber-500/25'
                            : tier === 'doctor_soon'
                            ? 'bg-blue-500/20 text-blue-700 dark:text-blue-400 border border-blue-500/25'
                            : 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/25'
                        }`}>
                          {tier.replace('_', ' ')}
                        </span>
                        {c.is_claimed && (
                          <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                            <Lock className="w-2.5 h-2.5 text-amber-500" />
                            {c.claimed_by_name?.split(' ')[0] || 'Claimed'}
                          </span>
                        )}
                      </div>

                      <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        {c.created_at ? formatDistanceToNow(new Date(c.created_at), { addSuffix: true }) : 'Now'}
                      </span>
                    </div>

                    <h4 className="font-medium text-sm text-foreground line-clamp-1 mb-1">
                      {c.chief_complaint || c.result?.clinical_summary?.chief_complaint || 'General Consultation'}
                    </h4>

                    <div className="flex items-center justify-between text-xs text-muted-foreground pt-1 border-t border-border/40">
                      <span>{c.patient_language || c.result?.patient_input?.language || 'Unknown'}</span>
                      {c.complaint_category && (
                        <span className="capitalize text-[10px] text-foreground/70">
                          {c.complaint_category.replace('_', ' ')}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Pane: Selected Case View (F3.3) */}
        <div className="lg:col-span-7">
          <CaseViewPanel
            consultation={selectedConsultation}
            currentUser={currentUser}
            onUpdate={refetch}
            doctorsRoster={doctorsRoster}
          />
        </div>
      </div>
    </div>
  );
}
