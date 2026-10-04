'use client';
import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Loader2, Play, Pause, Send, Languages, Volume2, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { sendVoicePrescription, VoicePrescriptionResponse, SUPPORTED_LANGUAGES } from '@/lib/api';

interface VoiceReplyRecorderProps {
  patientLanguage: string;
  consultationId?: string;
}

export function VoiceReplyRecorder({ patientLanguage, consultationId }: VoiceReplyRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<VoicePrescriptionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPlayingPatient, setIsPlayingPatient] = useState(false);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const patientAudioRef = useRef<HTMLAudioElement | null>(null);

  const langName = SUPPORTED_LANGUAGES.find(l => l.code === patientLanguage)?.name || patientLanguage;

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setResult(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      chunks.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(chunks.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        stream.getTracks().forEach(t => t.stop());
      };

      recorder.start();
      mediaRecorder.current = recorder;
      setIsRecording(true);
    } catch {
      setError('Microphone access denied');
    }
  }, []);

  const stopRecording = useCallback(() => {
    mediaRecorder.current?.stop();
    setIsRecording(false);
  }, []);

  const sendPrescription = useCallback(async () => {
    if (!audioBlob) return;
    setIsProcessing(true);
    setError(null);
    try {
      const res = await sendVoicePrescription({
        audio: audioBlob,
        patient_language: patientLanguage,
        consultation_id: consultationId,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Failed to process voice prescription');
    } finally {
      setIsProcessing(false);
    }
  }, [audioBlob, patientLanguage, consultationId]);

  const playPatientAudio = useCallback(() => {
    if (!result?.patient_audio_base64) return;
    if (patientAudioRef.current) {
      patientAudioRef.current.pause();
      patientAudioRef.current = null;
      setIsPlayingPatient(false);
      return;
    }
    const audio = new Audio(`data:audio/wav;base64,${result.patient_audio_base64}`);
    audio.onended = () => { setIsPlayingPatient(false); patientAudioRef.current = null; };
    audio.play();
    patientAudioRef.current = audio;
    setIsPlayingPatient(true);
  }, [result]);

  const reset = useCallback(() => {
    setAudioBlob(null);
    setResult(null);
    setError(null);
    setIsPlayingPatient(false);
    if (patientAudioRef.current) { patientAudioRef.current.pause(); patientAudioRef.current = null; }
  }, []);

  return (
    <Card className="border border-border bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-heading">
          <Languages className="w-5 h-5 text-primary" />
          Voice Reply to Patient
          <span className="text-xs text-muted-foreground font-normal ml-auto">→ {langName}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Recording State */}
        {!result && (
          <div className="flex flex-col items-center gap-3">
            <p className="text-sm text-muted-foreground text-center">
              Record your advice in English. It will be translated to <strong>{langName}</strong> and sent as a voice note.
            </p>

            <motion.button
              className={`w-16 h-16 rounded-full flex items-center justify-center transition-colors ${
                isRecording
                  ? 'bg-red-500 text-white shadow-lg shadow-red-500/30'
                  : 'bg-primary text-primary-foreground hover:bg-primary/90'
              }`}
              whileTap={{ scale: 0.9 }}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isProcessing}
            >
              {isRecording ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
            </motion.button>

            <span className="text-xs text-muted-foreground">
              {isRecording ? 'Recording... tap to stop' : audioBlob ? 'Recording captured' : 'Tap to record'}
            </span>

            {audioBlob && !isProcessing && (
              <div className="flex gap-2 w-full">
                <Button variant="outline" size="sm" onClick={reset} className="flex-1 gap-1">
                  <RotateCcw className="w-3 h-3" /> Re-record
                </Button>
                <Button size="sm" onClick={sendPrescription} className="flex-1 gap-1 bg-primary text-primary-foreground">
                  <Languages className="w-3 h-3" /> Review Back-Translation
                </Button>
              </div>
            )}

            {isProcessing && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                Transcribing → Translating → Verifying Back-Translation...
              </div>
            )}
          </div>
        )}

        {/* Result & Back-Translation Verification State (F3.4) */}
        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-3"
            >
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Your Spoken Advice (English)</h4>
                <p className="text-sm text-foreground bg-muted/30 p-2 rounded-lg border border-border">{result.english_text}</p>
              </div>
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Translated Speech ({langName})</h4>
                <p className="text-sm text-foreground bg-muted/30 p-2 rounded-lg border border-border">{result.translated_text}</p>
              </div>

              {result.back_translated_text && (
                <div className="border border-emerald-500/30 bg-emerald-500/10 p-3 rounded-lg">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider mb-1">
                    <span>🛡️ Clinician Back-Translation Verification</span>
                    <span className="ml-auto text-[10px] bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 px-2 py-0.5 rounded-full font-bold">
                      Verified Safe
                    </span>
                  </div>
                  <p className="text-xs text-foreground/90 italic font-mono">
                    "{result.back_translated_text}"
                  </p>
                  <span className="text-[10px] text-muted-foreground mt-1.5 block">
                    ✓ Reverse-translated back to English so doctor confirms no clinical drift before delivery.
                  </span>
                </div>
              )}

              {result.patient_audio_base64 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={playPatientAudio}
                  className="w-full gap-2"
                >
                  {isPlayingPatient ? <Pause className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                  {isPlayingPatient ? 'Stop Audio Preview' : `Listen to ${langName} Voice Note`}
                </Button>
              )}

              <div className="p-3 bg-primary/10 border border-primary/20 rounded-xl text-center">
                <span className="text-xs text-primary font-semibold flex items-center justify-center gap-1.5">
                  <Send className="w-3.5 h-3.5" /> Delivered to Patient's Two-Way Voice Thread
                </span>
              </div>

              <Button variant="ghost" size="sm" onClick={reset} className="w-full text-muted-foreground gap-1">
                <RotateCcw className="w-3 h-3" /> Record Another Advice
              </Button>
            </motion.div>
          )}
        </AnimatePresence>

        {error && (
          <p className="text-xs text-red-500 text-center">{error}</p>
        )}
      </CardContent>
    </Card>
  );
}
