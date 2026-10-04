'use client';
import { useState, useCallback, useRef } from 'react';
import {
  processAudio as apiProcessAudio,
  submitAudioAsync,
  getJobStatus,
  PipelineResult,
} from '@/lib/api';
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
  const inFlightRef = useRef(false);

  const applyStageTransition = useCallback((activeStageId: string) => {
    setCurrentStage(activeStageId);
    setStageProgress((prev) => {
      const next: Record<string, 'pending' | 'active' | 'complete' | 'error'> = { ...prev };
      let foundActive = false;
      for (const stage of PIPELINE_STAGES) {
        if (stage.id === activeStageId) {
          next[stage.id] = 'active';
          foundActive = true;
        } else if (!foundActive) {
          next[stage.id] = 'complete';
        } else {
          if (next[stage.id] !== 'complete') {
            next[stage.id] = 'pending';
          }
        }
      }
      return next;
    });
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
    profile_id?: string;
  }) => {
    if (inFlightRef.current) {
      console.warn("processAudio already running; ignoring duplicate call");
      return;
    }
    inFlightRef.current = true;
    setIsProcessing(true);
    setError(null);
    const initialProgress = PIPELINE_STAGES.reduce((acc, stage) => {
      acc[stage.id] = 'pending';
      return acc;
    }, {} as Record<string, 'pending' | 'active' | 'complete' | 'error'>);
    setStageProgress(initialProgress);

    try {
      applyStageTransition('audio_preprocessing');

      // Attempt F1.4 real asynchronous job processing with stage-by-stage status polling
      let finalResult: PipelineResult | null = null;

      try {
        const submission = await submitAudioAsync(params);
        if (submission && submission.job_id) {
          const jobId = submission.job_id;
          let jobCompleted = false;
          let attempts = 0;
          const maxAttempts = 90; // up to ~72 seconds

          while (!jobCompleted && attempts < maxAttempts) {
            await new Promise((r) => setTimeout(r, 800));
            attempts++;

            const statusRes = await getJobStatus(jobId);
            const status = statusRes?.status;

            if (status === 'PREPROCESSING') {
              applyStageTransition('audio_preprocessing');
            } else if (status === 'TRANSCRIBING') {
              applyStageTransition('speech_to_text');
            } else if (status === 'EXTRACTING') {
              applyStageTransition('medical_extraction');
            } else if (status === 'TRIAGING') {
              applyStageTransition('safety_screening');
            } else if (status === 'COMPLETED') {
              applyStageTransition('storing');
              finalResult = statusRes.result;
              jobCompleted = true;
              break;
            } else if (status === 'FAILED') {
              throw new Error(statusRes.error || 'Triage job processing failed');
            }
          }

          if (!jobCompleted && !finalResult) {
            throw new Error('Pipeline job timed out; falling back to synchronous execution');
          }
        }
      } catch (asyncErr: any) {
        console.warn('Async job polling unavailable or timed out; executing fallback:', asyncErr);
      }

      // Synchronous fallback if async did not complete
      if (!finalResult) {
        applyStageTransition('medical_extraction');
        finalResult = await apiProcessAudio(params);
      }

      applyStageTransition('storing');
      const cid = await storeResultToSupabase(finalResult);
      setConsultationId(cid || finalResult.request_id);
      setResult(finalResult);
      setStageProgress((prev) => {
        const next = { ...prev };
        PIPELINE_STAGES.forEach((s) => {
          next[s.id] = 'complete';
        });
        return next;
      });
    } catch (err: any) {
      console.error('Pipeline error:', err);
      setError(err.message || 'Pipeline processing failed');
      setStageProgress((prev) => {
        const next = { ...prev };
        Object.keys(next).forEach((k) => {
          if (next[k] === 'active') next[k] = 'error';
        });
        return next;
      });
    } finally {
      setIsProcessing(false);
      inFlightRef.current = false;
    }
  }, [applyStageTransition]);

  const reset = useCallback(() => {
    inFlightRef.current = false;
    setIsProcessing(false);
    setCurrentStage(null);
    setStageProgress({});
    setResult(null);
    setError(null);
    setConsultationId(null);
  }, []);

  return { processAudio, isProcessing, currentStage, stageProgress, result, error, consultationId, reset };
}
