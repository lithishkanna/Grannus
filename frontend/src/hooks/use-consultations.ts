'use client';
import { useState, useEffect, useCallback } from 'react';
import { getDoctorQueue } from '@/lib/api';

export function useConsultations() {
  const [consultations, setConsultations] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUnauthorized, setIsUnauthorized] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterByPriority, setFilterByPriority] = useState<string>('All');
  const [filterByDepartment, setFilterByDepartment] = useState<string>('All');

  const fetchConsultations = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    // Client-side guard: check token & role before making request
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('grannus_auth_token');
      const stored = localStorage.getItem('grannus_user');
      let isClinician = false;
      if (stored) {
        try {
          const user = JSON.parse(stored);
          isClinician = ['doctor', 'nurse', 'admin'].includes(user.role);
        } catch {
          // ignore json parse error
        }
      }

      if (!token || !isClinician) {
        setIsUnauthorized(true);
        setConsultations([]);
        setIsLoading(false);
        return;
      }
    }

    try {
      const res = await getDoctorQueue({
        tier: filterByPriority !== 'All' ? filterByPriority : undefined,
        department: filterByDepartment !== 'All' ? filterByDepartment : undefined,
        search: searchQuery || undefined,
      });

      if (res.unauthorized) {
        setIsUnauthorized(true);
        setConsultations([]);
        setIsLoading(false);
        return;
      }

      setIsUnauthorized(false);
      const formatted = (res.consultations || []).map((item: any) => ({
        id: item.id,
        created_at: item.created_at,
        status: item.status,
        urgency_tier: item.urgency_tier,
        department_id: item.department_id,
        complaint_category: item.complaint_category,
        chief_complaint: item.chief_complaint,
        patient_language: item.patient_language,
        assigned_doctor_id: item.assigned_doctor_id,
        is_claimed: item.is_claimed,
        claimed_by_name: item.claimed_by_name,
        claimed_by_id: item.claimed_by_id,
        lock_expires_at: item.lock_expires_at,
        result: item.full_result || {
          patient_input: {
            language: item.patient_language,
            transcript_original: item.original_transcript,
            transcript_english: item.english_transcript,
          },
          clinical_summary: {
            chief_complaint: item.chief_complaint,
          },
          priority: {
            urgency_tier: item.urgency_tier,
            level: item.urgency_tier === 'emergency' ? 'HIGH' : item.urgency_tier === 'doctor_today' ? 'HIGH' : item.urgency_tier === 'doctor_soon' ? 'MEDIUM' : 'LOW',
          },
        },
      }));

      setConsultations(formatted);
    } catch (err: any) {
      console.warn('Queue fetch info:', err.message || err);
      setError(err.message || 'Failed to load consultation queue.');
    } finally {
      setIsLoading(false);
    }
  }, [filterByPriority, filterByDepartment, searchQuery]);

  useEffect(() => {
    fetchConsultations();
  }, [fetchConsultations]);

  return {
    consultations,
    isLoading,
    isUnauthorized,
    error,
    refetch: fetchConsultations,
    filterByPriority,
    setFilterByPriority,
    filterByDepartment,
    setFilterByDepartment,
    searchQuery,
    setSearchQuery,
  };
}
