'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePipeline, PIPELINE_STAGES } from '@/hooks/use-pipeline';
import { PipelineFlow } from '@/components/pipeline/pipeline-flow';
import { ProcessingZen } from '@/components/pipeline/processing-zen';
import { Button } from '@/components/ui/button';
import { AlertCircle } from 'lucide-react';

export default function ProcessingPage() {
  const router = useRouter();
  const { processAudio, isProcessing, currentStage, stageProgress, consultationId, error, reset } = usePipeline();
  const [hasStarted, setHasStarted] = useState(false);

  useEffect(() => {
    if (hasStarted) return;
    
    const payloadStr = sessionStorage.getItem('grannus_pipeline_payload');
    if (!payloadStr) {
      router.push('/input');
      return;
    }

    try {
      const payload = JSON.parse(payloadStr);
      setHasStarted(true);

      // Convert base64 back to Blob
      fetch(payload.audio)
        .then(res => res.blob())
        .then(blob => {
          processAudio({
            audio: blob,
            language_code: payload.language_code === 'unknown' ? undefined : payload.language_code,
            doctor_preferred_language: payload.doctor_preferred_language,
            age: payload.age,
            gender: payload.gender,
            reported_duration: payload.reported_duration,
            known_conditions: payload.known_conditions,
            current_medications: payload.current_medications
          });
        });
    } catch (err) {
      console.error(err);
      router.push('/input');
    }
  }, [hasStarted, router, processAudio]);

  useEffect(() => {
    if (consultationId && !isProcessing) {
      // Small delay to show completion before navigation
      const timer = setTimeout(() => {
        sessionStorage.removeItem('grannus_pipeline_payload');
        router.push(`/results?id=${consultationId}`);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [consultationId, isProcessing, router]);

  const getLoadingText = () => {
    if (!currentStage) return 'Initializing...';
    const stage = PIPELINE_STAGES.find(s => s.id === currentStage);
    return stage ? `${stage.label}...` : 'Processing...';
  };

  const handleRetry = () => {
    reset();
    setHasStarted(false); // will re-trigger the initial effect
  };

  return (
    <div className="container mx-auto px-4 py-16 flex flex-col items-center justify-center min-h-[80vh]">
      {!error ? (
        <>
          <div className="mb-12 animate-gentle-fade-in">
            <ProcessingZen text={getLoadingText()} />
          </div>
          
          <div className="w-full animate-gentle-fade-in" style={{ animationDelay: '0.3s' }}>
            <PipelineFlow currentStage={currentStage} stageProgress={stageProgress} />
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center bg-card p-12 rounded-organic-2 shadow-ink-wash border border-red-200/20 max-w-md w-full animate-gentle-fade-in text-center">
          <div className="w-20 h-20 bg-red-100 dark:bg-red-900/30 text-red-600 rounded-full flex items-center justify-center mb-6">
            <AlertCircle className="w-10 h-10" />
          </div>
          <h2 className="text-2xl font-heading font-medium text-foreground mb-3">Processing Failed</h2>
          <p className="text-muted-foreground mb-8">{error}</p>
          <div className="flex gap-4 w-full">
            <Button variant="outline" className="flex-1" onClick={() => router.push('/input')}>
              Cancel
            </Button>
            <Button className="flex-1 bg-primary hover:bg-primary/90" onClick={handleRetry}>
              Try Again
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
