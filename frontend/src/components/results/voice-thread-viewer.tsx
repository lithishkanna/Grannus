'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageSquare,
  Volume2,
  Pause,
  RotateCcw,
  FastForward,
  Mic,
  MicOff,
  Send,
  Loader2,
  Languages,
  CheckCircle2,
  Clock,
  User,
  Stethoscope,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  VoiceThread,
  VoiceThreadMessage,
  getVoiceThread,
  replyToVoiceThread,
  SUPPORTED_LANGUAGES,
} from '@/lib/api';
import { formatDistanceToNow } from 'date-fns';

interface VoiceThreadViewerProps {
  consultationId: string;
  patientLanguage?: string;
}

export function VoiceThreadViewer({
  consultationId,
  patientLanguage = 'ta-IN',
}: VoiceThreadViewerProps) {
  const [thread, setThread] = useState<VoiceThread | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Audio playback state
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  // Recording state for patient reply
  const [isRecording, setIsRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [isSendingReply, setIsSendingReply] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);

  const langMeta = SUPPORTED_LANGUAGES.find((l) => l.code === patientLanguage);
  const langDisplay = langMeta?.nativeName
    ? `${langMeta.name} (${langMeta.nativeName})`
    : langMeta?.name || patientLanguage;

  const loadThread = useCallback(async () => {
    if (!consultationId) return;
    try {
      const data = await getVoiceThread(consultationId);
      setThread(data);
    } catch (err: any) {
      console.warn('Could not load voice thread:', err);
    } finally {
      setIsLoading(false);
    }
  }, [consultationId]);

  useEffect(() => {
    loadThread();
  }, [loadThread]);

  // Audio Playback Controls (F2.8: play with speed and repeat controls)
  const handlePlayAudio = (message: VoiceThreadMessage) => {
    if (!message.audio_base64) return;

    if (playingMessageId === message.message_id && audioPlayerRef.current) {
      if (audioPlayerRef.current.paused) {
        audioPlayerRef.current.play();
      } else {
        audioPlayerRef.current.pause();
        setPlayingMessageId(null);
      }
      return;
    }

    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
    }

    const audio = new Audio(`data:audio/wav;base64,${message.audio_base64}`);
    audio.playbackRate = playbackSpeed;
    audio.onended = () => setPlayingMessageId(null);
    audio.onerror = () => setPlayingMessageId(null);
    audio.play();

    audioPlayerRef.current = audio;
    setPlayingMessageId(message.message_id);
  };

  const handleRepeatAudio = () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.currentTime = 0;
      audioPlayerRef.current.playbackRate = playbackSpeed;
      audioPlayerRef.current.play();
    }
  };

  const handleToggleSpeed = () => {
    const nextSpeed = playbackSpeed === 1.0 ? 0.75 : playbackSpeed === 0.75 ? 1.25 : 1.0;
    setPlaybackSpeed(nextSpeed);
    if (audioPlayerRef.current) {
      audioPlayerRef.current.playbackRate = nextSpeed;
    }
  };

  // Recording Controls
  const startRecording = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      recordedChunksRef.current = [];

      rec.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data);
      };

      rec.onstop = () => {
        const blob = new Blob(recordedChunksRef.current, { type: 'audio/webm' });
        setRecordedBlob(blob);
        stream.getTracks().forEach((t) => t.stop());
      };

      rec.start();
      mediaRecorderRef.current = rec;
      setIsRecording(true);
    } catch {
      setError('Microphone permission denied. Please allow microphone access to record.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleSendReply = async () => {
    if (!recordedBlob || !consultationId) return;
    setIsSendingReply(true);
    setError(null);
    try {
      await replyToVoiceThread({
        consultationId,
        audio: recordedBlob,
        patientLanguage,
      });
      setRecordedBlob(null);
      await loadThread();
    } catch (err: any) {
      setError(err.message || 'Failed to send voice reply. Please try again.');
    } finally {
      setIsSendingReply(false);
    }
  };

  return (
    <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
      <div className="flex items-center justify-between pb-4 border-b border-border/60 mb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
            <MessageSquare className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-heading font-semibold text-lg text-foreground">
              Doctor–Patient Voice Thread
            </h3>
            <p className="text-xs text-muted-foreground">
              Asynchronous two-way translated voice dialogue • {langDisplay}
            </p>
          </div>
        </div>

        <span className="text-xs text-muted-foreground px-2.5 py-1 rounded-full bg-secondary/60">
          {thread?.messages?.length || 0} messages
        </span>
      </div>

      {/* Messages stream */}
      <div className="space-y-4 mb-6 max-h-[400px] overflow-y-auto pr-1">
        {(!thread?.messages || thread.messages.length === 0) ? (
          <div className="p-6 text-center border border-dashed border-border rounded-xl text-muted-foreground text-xs">
            No voice messages in this thread yet. When a doctor leaves advice, you will hear it in {langDisplay}.
          </div>
        ) : (
          thread.messages.map((msg) => {
            const isDoctor = msg.sender === 'doctor';
            const isPlaying = playingMessageId === msg.message_id;

            return (
              <div
                key={msg.message_id}
                className={`p-4 rounded-xl border transition-all ${
                  isDoctor
                    ? 'bg-primary/5 border-primary/20 ml-0 mr-8'
                    : 'bg-muted/40 border-border mr-0 ml-8'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                        isDoctor
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-secondary text-secondary-foreground'
                      }`}
                    >
                      {isDoctor ? <Stethoscope className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
                    </div>
                    <span className="text-xs font-semibold text-foreground">
                      {isDoctor ? 'Doctor Advice' : 'Patient Reply'}
                    </span>
                  </div>

                  <span className="text-[10px] text-muted-foreground">
                    {msg.created_at ? formatDistanceToNow(new Date(msg.created_at), { addSuffix: true }) : 'Recent'}
                  </span>
                </div>

                {/* Primary Spoken Text */}
                <p className="text-sm font-medium text-foreground mb-2">
                  {msg.translated_text || msg.original_text}
                </p>

                {/* English Subtitle / Original if different */}
                {msg.original_text && msg.original_text !== msg.translated_text && (
                  <p className="text-xs text-muted-foreground italic mb-3">
                    Original ({msg.original_language}): "{msg.original_text}"
                  </p>
                )}

                {/* Audio controls for Doctor Voice Note (F2.8) */}
                {isDoctor && msg.audio_base64 && (
                  <div className="flex items-center gap-2 pt-2 border-t border-border/50 flex-wrap">
                    <Button
                      variant={isPlaying ? 'destructive' : 'default'}
                      size="sm"
                      onClick={() => handlePlayAudio(msg)}
                      className="gap-1.5 rounded-full text-xs h-8 px-4"
                    >
                      {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                      {isPlaying ? 'Pause' : 'Play Voice Note'}
                    </Button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRepeatAudio}
                      className="gap-1 rounded-full text-xs h-8 px-3"
                      title="Replay from start"
                    >
                      <RotateCcw className="w-3 h-3" /> Repeat
                    </Button>

                    <button
                      onClick={handleToggleSpeed}
                      className="text-xs font-semibold px-2.5 py-1 rounded-full bg-secondary text-secondary-foreground border border-border hover:bg-secondary/80 transition-all"
                      title="Change playback speed"
                    >
                      {playbackSpeed}x Speed
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Record reply section */}
      <div className="pt-4 border-t border-border/60">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Reply to Doctor by Voice ({langDisplay})
        </h4>

        <div className="flex flex-col sm:flex-row items-center gap-3">
          <Button
            type="button"
            variant={isRecording ? 'destructive' : 'outline'}
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isSendingReply}
            className="w-full sm:w-auto gap-2 rounded-xl h-11 px-5"
          >
            {isRecording ? (
              <>
                <MicOff className="w-4 h-4 animate-pulse" />
                <span>Stop Recording</span>
              </>
            ) : (
              <>
                <Mic className="w-4 h-4 text-primary" />
                <span>{recordedBlob ? 'Re-record Spoken Reply' : 'Record Spoken Reply'}</span>
              </>
            )}
          </Button>

          {recordedBlob && !isRecording && (
            <Button
              type="button"
              onClick={handleSendReply}
              disabled={isSendingReply}
              className="w-full sm:w-auto gap-2 rounded-xl h-11 px-6 bg-primary text-primary-foreground shadow-sm"
            >
              {isSendingReply ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Translating & Sending...</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>Send Voice Reply</span>
                </>
              )}
            </Button>
          )}

          {isRecording && (
            <span className="text-xs text-destructive font-medium animate-pulse">
              ● Recording in {langDisplay}... Tap stop when done
            </span>
          )}
        </div>

        {error && (
          <p className="text-xs text-destructive mt-3">{error}</p>
        )}
      </div>
    </div>
  );
}
