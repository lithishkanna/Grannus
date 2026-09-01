'use client';
import { useState, useCallback } from 'react';
import { processAudio as apiProcessAudio, PipelineResult } from '@/lib/api';
import { storeResultToSupabase } from '@/lib/store-result';

export const PIPELINE_STAGES = [
  { id: 'audio_preprocessing', label: 'Audio Preprocessing', icon: 'AudioWaveform', duration: 2000 },
  { id: 'speech_to_text', label: 'Speech-to-Text', icon: 'Languages', duration: 5000 },
  { id: 'medical_extraction', label: 'Medical Extraction', icon: 'Brain', duration: 8000 },
  { id: 'safety_screening', label: 'Safety Screening', icon: 'ShieldCheck', duration: 2000 },
  { id: 'priority_assessment', label: 'Priority Assessment', icon: 'Scale', duration: 2000 },
  { id: 'translation', label: 'Translation', icon: 'Globe', duration: 3000 },
  { id: 'storing', label: 'Storing Results', icon: 'Database', duration: 1000 },
] as const;

export function usePipeline() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [stageProgress, setStageProgress] = useState<Record<string, 'pending' | 'active' | 'complete' | 'error'>>({});
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [consultationId, setConsultationId] = useState<string | null>(null);

  const simulateStages = useCallback(async () => {
    let active = true;
    for (const stage of PIPELINE_STAGES) {
      if (!active) break;
      setCurrentStage(stage.id);
      setStageProgress(prev => ({ ...prev, [stage.id]: 'active' }));
      
      if (stage.id !== 'storing') {
         await new Promise(resolve => setTimeout(resolve, stage.duration));
         setStageProgress(prev => ({ ...prev, [stage.id]: 'complete' }));
      }
    }
  }, []);

  const processAudio = useCallback(async (params: {
    audio: Blob;
    language_code?: string;
    doctor_preferred_language?: string;
    age?: string;
    gender?: string;
    reported_duration?: string;
    known_conditions?: string;
    current_medications?: string;
  }) => {
    setIsProcessing(true);
    setError(null);
    const initialProgress = PIPELINE_STAGES.reduce((acc, stage) => {
      acc[stage.id] = 'pending';
      return acc;
    }, {} as Record<string, 'pending' | 'active' | 'complete' | 'error'>);
    setStageProgress(initialProgress);

    try {
      // Start fake stage simulation visually
      simulateStages();

      // Actually call backend
      const res = await apiProcessAudio(params);
      
      // Fast forward to storing if it finishes early
      setCurrentStage('storing');
      setStageProgress(prev => {
        const next = { ...prev };
        PIPELINE_STAGES.forEach(s => {
          if (s.id !== 'storing') next[s.id] = 'complete';
        });
        next['storing'] = 'active';
        return next;
      });

      const cid = await storeResultToSupabase(res);
      setConsultationId(cid);
      setResult(res);
      setStageProgress(prev => ({ ...prev, storing: 'complete' }));
      
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Pipeline processing failed');
      setStageProgress(prev => {
         const next = { ...prev };
         Object.keys(next).forEach(k => {
            if (next[k] === 'active') next[k] = 'error';
         });
         return next;
      });
    } finally {
      setIsProcessing(false);
    }
  }, [simulateStages]);

  const reset = useCallback(() => {
    setIsProcessing(false);
    setCurrentStage(null);
    setStageProgress({});
    setResult(null);
    setError(null);
    setConsultationId(null);
  }, []);

  return { processAudio, isProcessing, currentStage, stageProgress, result, error, consultationId, reset };
}
