'use client';
import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import { PipelineResult } from '@/lib/api';
import { PriorityBadge } from '@/components/results/priority-badge';
import { SymptomCard } from '@/components/results/symptom-card';
import { SafetyFlags } from '@/components/results/safety-flags';
import { TranscriptView } from '@/components/results/transcript-view';
import { TranslationCard } from '@/components/results/translation-card';
import { HomeRemedy } from '@/components/results/home-remedy';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Plus } from 'lucide-react';
import { motion } from 'framer-motion';

function ResultsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = searchParams?.get('id');
  
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) {
      router.push('/input');
      return;
    }

    const fetchResult = async () => {
      try {
        const { data, error } = await supabase
          .from('pipeline_results')
          .select('full_result')
          .eq('consultation_id', id)
          .single();

        if (error) throw error;
        if (data) setResult(data.full_result);
      } catch (err) {
        console.error('Error fetching result:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchResult();
  }, [id, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
          <p className="text-muted-foreground">Loading results...</p>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center px-4">
        <h2 className="text-2xl font-heading font-medium">Result not found</h2>
        <p className="text-muted-foreground">The consultation you're looking for doesn't exist or you don't have access.</p>
        <Button onClick={() => router.push('/input')}>Go to Voice Input</Button>
      </div>
    );
  }

  const { patient_input, clinical_summary, safety_screening, priority, doctor_translated_summary, home_remedy_guidance } = result;
  const hasCriticalFlags = safety_screening.red_flags.some((f: any) => f.severity === 'critical');

  return (
    <div className="pb-24 animate-gentle-fade-in">
      {/* Priority Banner */}
      <div className="w-full bg-card border-b border-border shadow-sm py-8 px-4 mb-8">
        <div className="container mx-auto max-w-5xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <h1 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">Priority Assessment</h1>
            <PriorityBadge level={priority.level} confidence={priority.confidence} size="lg" />
            <div className="mt-3 flex flex-wrap gap-2">
              {priority.reasons.map((r: string, i: number) => (
                <span key={i} className="text-sm text-foreground bg-secondary/50 px-3 py-1 rounded-full">{r}</span>
              ))}
            </div>
          </div>
          
          <div className="flex items-center gap-3 w-full md:w-auto">
            <Button variant="outline" className="flex-1 md:flex-none gap-2 rounded-full border-border bg-background" onClick={() => router.push('/dashboard')}>
              <ArrowLeft className="w-4 h-4" /> Dashboard
            </Button>
            <Button className="flex-1 md:flex-none gap-2 rounded-full bg-primary" onClick={() => router.push('/input')}>
              <Plus className="w-4 h-4" /> New
            </Button>
          </div>
        </div>
      </div>

      <div className="container mx-auto max-w-5xl px-4 space-y-10">
        {/* Doctor Summary / Home Remedies depending on priority */}
        {['HIGH', 'MEDIUM', 'PENDING_REVIEW'].includes(priority.level) && doctor_translated_summary && (
          <motion.section initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.1 }}>
            <TranslationCard data={doctor_translated_summary} />
          </motion.section>
        )}

        {priority.level === 'LOW' && home_remedy_guidance && (
          <motion.section initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.1 }}>
            <HomeRemedy data={home_remedy_guidance} />
          </motion.section>
        )}

        {/* Safety Flags */}
        {safety_screening.red_flags && safety_screening.red_flags.length > 0 && (
          <motion.section initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.2 }}>
            <SafetyFlags flags={safety_screening.red_flags as any} hasCritical={hasCriticalFlags} />
          </motion.section>
        )}

        {/* Transcript */}
        <motion.section initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.3 }}>
          <TranscriptView 
            original={patient_input.transcript_original} 
            english={patient_input.transcript_english} 
            language={patient_input.language} 
          />
        </motion.section>

        {/* Clinical Summary */}
        <motion.section initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.4 }} className="space-y-6">
          <div>
            <h2 className="text-2xl font-heading font-medium text-foreground mb-6">Clinical Extraction</h2>
            
            <div className="bg-card p-6 rounded-xl border border-border shadow-sm mb-6">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">Chief Complaint</h3>
              <p className="text-xl text-foreground font-medium">{clinical_summary.chief_complaint || 'Not specified'}</p>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">Identified Symptoms</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {clinical_summary.symptoms && clinical_summary.symptoms.length > 0 ? (
                clinical_summary.symptoms.map((s, i) => (
                  <SymptomCard key={i} symptom={s as any} />
                ))
              ) : (
                <div className="col-span-full p-6 text-center border border-dashed border-border rounded-xl text-muted-foreground">
                  No symptoms identified in the audio.
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
            <div className="bg-muted/20 p-5 rounded-xl border border-border">
              <h4 className="font-medium mb-3 flex items-center gap-2">Conditions</h4>
              <ul className="space-y-2">
                {clinical_summary.existing_conditions?.length ? clinical_summary.existing_conditions.map((c, i) => (
                  <li key={i} className="text-sm text-foreground flex gap-2"><span className="text-primary">•</span>{c}</li>
                )) : <li className="text-sm text-muted-foreground italic">None reported</li>}
              </ul>
            </div>
            
            <div className="bg-muted/20 p-5 rounded-xl border border-border">
              <h4 className="font-medium mb-3 flex items-center gap-2">Medications</h4>
              <ul className="space-y-2">
                {clinical_summary.medications?.length ? clinical_summary.medications.map((m, i) => (
                  <li key={i} className="text-sm text-foreground flex gap-2"><span className="text-primary">•</span>{m}</li>
                )) : <li className="text-sm text-muted-foreground italic">None reported</li>}
              </ul>
            </div>
            
            <div className="bg-muted/20 p-5 rounded-xl border border-border">
              <h4 className="font-medium mb-3 flex items-center gap-2">Allergies</h4>
              <ul className="space-y-2">
                {clinical_summary.allergies?.length ? clinical_summary.allergies.map((a, i) => (
                  <li key={i} className="text-sm text-foreground flex gap-2"><span className="text-primary">•</span>{a}</li>
                )) : <li className="text-sm text-muted-foreground italic">None reported</li>}
              </ul>
            </div>
          </div>
        </motion.section>
      </div>
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-[60vh]"><div className="animate-pulse w-12 h-12 border-4 border-primary/30 border-t-primary rounded-full animate-spin" /></div>}>
      <ResultsContent />
    </Suspense>
  );
}
