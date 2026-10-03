'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useConsultations } from '@/hooks/use-consultations';
import { StatsOverview } from '@/components/dashboard/stats-overview';
import { ConsultationTable } from '@/components/dashboard/consultation-table';
import { PriorityFilter } from '@/components/dashboard/priority-filter';
import { DetailDrawer } from '@/components/dashboard/detail-drawer';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, Plus, ShieldCheck, LogIn, LogOut } from 'lucide-react';

export default function DashboardPage() {
  const router = useRouter();
  const { 
    consultations, isLoading, error, 
    filterByPriority, setFilterByPriority, 
    searchQuery, setSearchQuery 
  } = useConsultations();

  const [selectedConsultation, setSelectedConsultation] = useState<any | null>(null);
  const [currentUser, setCurrentUser] = useState<any | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('grannus_user');
      if (stored) {
        setCurrentUser(JSON.parse(stored));
      }
    } catch (e) {
      console.error('Failed to load user session', e);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('grannus_auth_token');
    localStorage.removeItem('grannus_user');
    setCurrentUser(null);
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-12 flex flex-col items-center justify-center min-h-[60vh]">
        <div className="w-10 h-10 border-4 border-primary/30 border-t-primary rounded-full animate-spin mb-4" />
        <p className="text-muted-foreground">Loading dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-12 text-center text-red-500">
        Error loading dashboard: {error}
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-12 max-w-6xl animate-gentle-fade-in">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-heading font-medium text-foreground">Doctor Dashboard</h1>
            {currentUser?.is_verified_doctor ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
                <ShieldCheck className="w-3.5 h-3.5" />
                Verified RMP: {currentUser.doctor_registration_number}
              </span>
            ) : null}
          </div>
          <p className="text-muted-foreground mt-1">Overview of patient consultations and AI triage.</p>
        </div>
        <div className="flex items-center gap-3">
          {currentUser ? (
            <Button variant="outline" size="sm" onClick={handleLogout} className="gap-1.5 rounded-full text-xs">
              <LogOut className="w-3.5 h-3.5" /> Sign Out
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={() => router.push('/login')} className="gap-1.5 rounded-full text-xs">
              <LogIn className="w-3.5 h-3.5" /> Clinician Login
            </Button>
          )}
          <Button onClick={() => router.push('/input')} className="gap-2 rounded-full px-6">
            <Plus className="w-4 h-4" /> New Consultation
          </Button>
        </div>
      </div>

      <StatsOverview consultations={consultations} />

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-2">
        <PriorityFilter selected={filterByPriority} onChange={setFilterByPriority} />
        
        <div className="relative w-full md:w-64 mb-6 md:mb-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input 
            placeholder="Search symptoms, language..." 
            className="pl-9 rounded-full bg-card"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <ConsultationTable consultations={consultations} onSelect={setSelectedConsultation} />

      <DetailDrawer 
        consultation={selectedConsultation} 
        isOpen={!!selectedConsultation} 
        onClose={() => setSelectedConsultation(null)} 
      />
    </div>
  );
}
