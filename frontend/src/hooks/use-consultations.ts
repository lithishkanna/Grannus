'use client';
import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/lib/supabase';

export function useConsultations() {
  const [consultations, setConsultations] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterByPriority, setFilterByPriority] = useState<string>('All');

  const fetchConsultations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Fetch consultations with pipeline results and summaries
      const { data, error: fetchError } = await supabase
        .from('pipeline_results')
        .select(`
          full_result,
          consultation_id,
          consultations (
            created_at,
            status
          )
        `)
        .order('created_at', { ascending: false });

      if (fetchError) throw fetchError;

      let formatted = data.map((item: any) => ({
        id: item.consultation_id,
        created_at: item.consultations?.created_at,
        status: item.consultations?.status,
        result: item.full_result
      }));

      if (filterByPriority !== 'All') {
        formatted = formatted.filter((item: any) => item.result.priority?.level === filterByPriority);
      }

      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        formatted = formatted.filter((item: any) => 
          item.result.clinical_summary?.chief_complaint?.toLowerCase().includes(query) ||
          item.result.patient_input?.language?.toLowerCase().includes(query)
        );
      }

      setConsultations(formatted);
    } catch (err: any) {
      console.error(err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [filterByPriority, searchQuery]);

  useEffect(() => {
    fetchConsultations();
  }, [fetchConsultations]);

  return {
    consultations,
    isLoading,
    error,
    refetch: fetchConsultations,
    filterByPriority,
    setFilterByPriority,
    searchQuery,
    setSearchQuery
  };
}
