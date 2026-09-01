'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useConsultations } from '@/hooks/use-consultations';
import { StatsOverview } from '@/components/dashboard/stats-overview';
import { ConsultationTable } from '@/components/dashboard/consultation-table';
import { PriorityFilter } from '@/components/dashboard/priority-filter';
import { DetailDrawer } from '@/components/dashboard/detail-drawer';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, Plus } from 'lucide-react';

export default function DashboardPage() {
  const router = useRouter();
  const { 
    consultations, isLoading, error, 
    filterByPriority, setFilterByPriority, 
    searchQuery, setSearchQuery 
  } = useConsultations();

  const [selectedConsultation, setSelectedConsultation] = useState<any | null>(null);

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
          <h1 className="text-3xl font-heading font-medium text-foreground mb-1">Doctor Dashboard</h1>
          <p className="text-muted-foreground">Overview of patient consultations and AI triage.</p>
        </div>
        <Button onClick={() => router.push('/input')} className="gap-2 rounded-full px-6">
          <Plus className="w-4 h-4" /> New Consultation
        </Button>
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
