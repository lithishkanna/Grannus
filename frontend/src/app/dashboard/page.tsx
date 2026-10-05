'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useConsultations } from '@/hooks/use-consultations';
import { StatsOverview } from '@/components/dashboard/stats-overview';
import { PriorityFilter } from '@/components/dashboard/priority-filter';
import { CaseViewPanel } from '@/components/dashboard/case-view-panel';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toggleDoctorAvailability, getDoctorRoster, loginStaff } from '@/lib/api';
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
  Stethoscope,
  ArrowRight,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const HOSPITAL_CLINICIANS = [
  {
    name: 'Dr. Rajan K., MD',
    role: 'doctor',
    title: 'General Medicine (HOD)',
    email: 'dr.rajan@hospital.in',
    regNo: 'TNMC-48291',
    council: 'Tamil Nadu Medical Council',
    languages: 'Tamil, English, Hindi',
  },
  {
    name: 'Dr. Priya Sundaram, DM',
    role: 'doctor',
    title: 'Cardiology Specialist',
    email: 'dr.priya@hospital.in',
    regNo: 'TNMC-54321',
    council: 'Tamil Nadu Medical Council',
    languages: 'Tamil, English',
  },
  {
    name: 'Dr. Vikram Patel, MD',
    role: 'doctor',
    title: 'Pediatrics Consultant',
    email: 'dr.vikram@hospital.in',
    regNo: 'GMC-39104',
    council: 'Gujarat Medical Council',
    languages: 'Hindi, English, Telugu',
  },
  {
    name: 'Dr. Meenakshi Iyer, MS',
    role: 'doctor',
    title: 'OB-GYN Senior Consultant',
    email: 'dr.meenakshi@hospital.in',
    regNo: 'TNMC-61245',
    council: 'Tamil Nadu Medical Council',
    languages: 'Tamil, English',
  },
  {
    name: 'Staff Nurse Deepa R.',
    role: 'nurse',
    title: 'Triage Lead & ER Coordinator',
    email: 'nurse.mary@hospital.in',
    password: 'grannus_nurse_2026',
    languages: 'Tamil, English',
  },
];

export default function DashboardPage() {
  const router = useRouter();
  const {
    consultations,
    isLoading,
    isUnauthorized,
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
      if (token && stored) {
        const u = JSON.parse(stored);
        if (['doctor', 'nurse', 'admin'].includes(u.role)) {
          setCurrentUser(u);
          if (typeof u.is_on_duty === 'boolean') {
            setIsOnDuty(u.is_on_duty);
          }
          getDoctorRoster()
            .then((res) => {
              if (res && res.doctors) setDoctorsRoster(res.doctors);
            })
            .catch((e) => console.warn('Could not load roster', e));
        }
      }
    } catch (e) {
      console.warn('Session check:', e);
    }
  }, []);

  const handleQuickLogin = async (doctor: (typeof HOSPITAL_CLINICIANS)[0]) => {
    try {
      const payload: Record<string, any> = {
        email: doctor.email,
        user_id: doctor.email,
        password: doctor.password || 'grannus_secure_doctor_2026',
        role: doctor.role,
      };
      if (doctor.role === 'doctor') {
        payload.doctor_registration_number = doctor.regNo;
        payload.state_medical_council = doctor.council || 'Tamil Nadu Medical Council';
      }
      const data = await loginStaff(payload);
      const user = {
        user_id: data.user_id,
        email: doctor.email,
        full_name: doctor.name,
        role: data.role,
        is_verified_doctor: data.is_verified_doctor,
        doctor_registration_number: data.doctor_registration_number || doctor.regNo,
        is_on_duty: true,
      };
      localStorage.setItem('grannus_user', JSON.stringify(user));
      setCurrentUser(user);
      setIsOnDuty(true);
      await refetch();
      getDoctorRoster()
        .then((res) => {
          if (res && res.doctors) setDoctorsRoster(res.doctors);
        })
        .catch(() => {});
    } catch (err: any) {
      console.warn('Quick login failed:', err);
    }
  };

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

  if (!currentUser || isUnauthorized) {
    return (
      <div className="container mx-auto px-4 py-12 max-w-3xl animate-gentle-fade-in">
        <div className="text-center mb-8">
          <div className="inline-flex p-3 bg-primary/10 rounded-full mb-3 text-primary">
            <Stethoscope className="w-8 h-8" />
          </div>
          <h1 className="text-2xl md:text-3xl font-heading font-semibold text-foreground">
            Hospital Clinician Portal
          </h1>
          <p className="text-muted-foreground text-sm mt-1.5 max-w-md mx-auto">
            Telemedicine Practice Guidelines 2020 Registered Medical Practitioner Access. Select a duty clinician to open the live triage queue.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {HOSPITAL_CLINICIANS.map((doc) => (
            <div
              key={doc.email}
              className="p-4 rounded-xl border border-border bg-card hover:border-primary/50 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-foreground text-sm">{doc.name}</span>
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-primary/10 text-primary">
                    {doc.role}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{doc.title}</p>
                {doc.regNo && (
                  <p className="text-[11px] font-mono text-muted-foreground/80 mt-1">
                    Reg: {doc.regNo}
                  </p>
                )}
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Languages: {doc.languages}
                </p>
              </div>
              <Button
                size="sm"
                className="mt-3.5 w-full text-xs font-medium gap-1.5"
                onClick={() => handleQuickLogin(doc)}
              >
                <LogIn className="w-3.5 h-3.5" />
                Open Workstation
              </Button>
            </div>
          ))}
        </div>

        <div className="mt-6 text-center">
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push('/login')}
            className="text-xs text-muted-foreground"
          >
            Sign in with custom password / credentials
          </Button>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-12 text-center text-red-500">
        <p className="mb-3">Error loading queue: {error}</p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
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
