'use client';
import { useAudioRecorder } from '@/hooks/use-audio-recorder';
import { Waveform } from './waveform';
import { Mic, Square, Pause, Play, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { motion } from 'framer-motion';
import { useEffect } from 'react';

export function AudioRecorder({ onAudioReady }: { onAudioReady: (blob: Blob) => void }) {
  const { 
    isRecording, isPaused, duration, audioUrl, audioBlob,
    startRecording, stopRecording, pauseRecording, resumeRecording, resetRecording 
  } = useAudioRecorder();

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const handleStop = () => {
    stopRecording();
  };

  useEffect(() => {
    if (audioBlob) onAudioReady(audioBlob);
  }, [audioBlob, onAudioReady]);

  return (
    <div className="flex flex-col items-center justify-center p-8 bg-card rounded-organic-2 shadow-ink-wash border border-border gap-8 min-h-[350px]">
      {!audioUrl ? (
        <>
          <div className="text-4xl font-mono text-foreground font-medium tracking-wider">
            {formatTime(duration)}
          </div>
          
          <Waveform isRecording={isRecording && !isPaused} isPlaying={false} />

          <div className="flex items-center gap-4">
            {isRecording ? (
              <>
                <Button 
                  variant="outline" 
                  size="icon" 
                  className="w-14 h-14 rounded-full border-2 border-primary/20 text-primary hover:bg-primary/10"
                  onClick={isPaused ? resumeRecording : pauseRecording}
                >
                  {isPaused ? <Play className="w-6 h-6" /> : <Pause className="w-6 h-6" />}
                </Button>
                
                <Button 
                  variant="destructive" 
                  size="icon" 
                  className="w-20 h-20 rounded-organic-1 bg-destructive hover:bg-destructive/90 shadow-lg"
                  onClick={handleStop}
                >
                  <Square className="w-8 h-8 fill-current" />
                </Button>
              </>
            ) : (
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Button 
                  size="icon" 
                  className="w-24 h-24 rounded-organic-3 bg-primary hover:bg-primary/90 shadow-ink-wash-lg text-primary-foreground"
                  onClick={startRecording}
                >
                  <Mic className="w-10 h-10" />
                </Button>
              </motion.div>
            )}
          </div>
          
          <p className="text-sm text-muted-foreground">
            {isRecording ? (isPaused ? 'Recording paused' : 'Recording in progress...') : 'Tap to start recording'}
          </p>
        </>
      ) : (
        <div className="flex flex-col items-center gap-6 w-full max-w-sm animate-gentle-fade-in">
          <div className="w-full bg-background rounded-full px-4 py-2 border border-border shadow-inner">
             <audio src={audioUrl} controls className="w-full h-10" />
          </div>
          
          <Button variant="outline" onClick={resetRecording} className="gap-2 rounded-full px-6">
            <RotateCcw className="w-4 h-4" />
            Record Again
          </Button>
        </div>
      )}
    </div>
  );
}
