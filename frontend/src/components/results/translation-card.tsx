'use client';
import { DoctorTranslatedSummary } from '@/lib/api';
import { FileText, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState, useEffect } from 'react';

export function TranslationCard({ data }: { data: DoctorTranslatedSummary }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [audio, setAudio] = useState<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (audio) {
        audio.pause();
      }
    };
  }, [audio]);

  const handlePlay = () => {
    if (isPlaying && audio) {
      audio.pause();
      setIsPlaying(false);
    } else if (data.audio_base64) {
      if (!audio) {
        const newAudio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
        newAudio.onended = () => setIsPlaying(false);
        setAudio(newAudio);
        newAudio.play();
      } else {
        audio.play();
      }
      setIsPlaying(true);
    }
  };

  return (
    <div className="bg-[#f0f4f8] dark:bg-[#1a202c] rounded-2xl p-6 md:p-8 border border-[#e2e8f0] dark:border-[#2d3748] shadow-sm">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 pb-4 border-b border-[#e2e8f0] dark:border-[#2d3748]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#5b6b7a] rounded-full flex items-center justify-center text-white">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-heading text-xl font-medium text-[#2d3748] dark:text-[#e2e8f0]">Doctor's Summary</h3>
            <p className="text-sm text-[#718096] dark:text-[#a0aec0]">Translated to {data.language}</p>
          </div>
        </div>
        
        {data.audio_base64 && (
          <Button onClick={handlePlay} variant="outline" className="gap-2 bg-white dark:bg-[#2d3748] text-[#5b6b7a] dark:text-[#e2e8f0] border-[#cbd5e0] dark:border-[#4a5568] hover:bg-[#e2e8f0] dark:hover:bg-[#4a5568] rounded-full px-6">
            <Play className={`w-4 h-4 ${isPlaying ? 'fill-current' : ''}`} />
            {isPlaying ? 'Pause Audio' : 'Listen'}
          </Button>
        )}
      </div>

      <div className="space-y-6 text-[#4a5568] dark:text-[#cbd5e0]">
        <div>
          <h4 className="text-xs font-semibold text-[#a0aec0] dark:text-[#718096] uppercase tracking-wider mb-2">Chief Complaint</h4>
          <p className="text-lg font-medium text-[#2d3748] dark:text-[#f7fafc]">{data.chief_complaint || 'Not specified'}</p>
        </div>
        
        <div>
          <h4 className="text-xs font-semibold text-[#a0aec0] dark:text-[#718096] uppercase tracking-wider mb-2">Symptoms</h4>
          <p className="leading-relaxed">{data.symptoms_summary || 'No symptoms summarized'}</p>
        </div>

        {data.red_flags_summary && (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-xl border border-red-100 dark:border-red-900/30 text-red-800 dark:text-red-300">
            <h4 className="text-xs font-semibold uppercase tracking-wider mb-2 text-red-600 dark:text-red-400">Red Flags</h4>
            <p>{data.red_flags_summary}</p>
          </div>
        )}
      </div>
    </div>
  );
}
