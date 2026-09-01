'use client';
import { motion } from 'framer-motion';
import { AudioWaveform, Languages, Brain, ShieldCheck, Scale, Globe, Database, Check, X } from 'lucide-react';

const icons = {
  AudioWaveform, Languages, Brain, ShieldCheck, Scale, Globe, Database
};

export type StageStatus = 'pending' | 'active' | 'complete' | 'error';

interface StageIndicatorProps {
  label: string;
  iconName: keyof typeof icons;
  status: StageStatus;
  isLast?: boolean;
}

export function StageIndicator({ label, iconName, status, isLast = false }: StageIndicatorProps) {
  const Icon = icons[iconName];

  const getStatusColors = () => {
    switch (status) {
      case 'active': return 'bg-amber-100 text-amber-600 border-amber-400 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-700';
      case 'complete': return 'bg-emerald-100 text-emerald-600 border-emerald-400 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-700';
      case 'error': return 'bg-red-100 text-red-600 border-red-400 dark:bg-red-900/30 dark:text-red-400 dark:border-red-700';
      default: return 'bg-stone-100 text-stone-400 border-stone-200 dark:bg-stone-800 dark:text-stone-500 dark:border-stone-700';
    }
  };

  return (
    <div className="flex flex-col md:flex-row items-center w-full md:w-auto relative group">
      <div className="flex flex-col items-center">
        <motion.div 
          className={`w-14 h-14 rounded-full border-2 flex items-center justify-center relative z-10 transition-colors duration-500 ${getStatusColors()}`}
          animate={status === 'active' ? { scale: [1, 1.05, 1], boxShadow: ["0 0 0 rgba(0,0,0,0)", "0 0 15px rgba(0,0,0,0.1)", "0 0 0 rgba(0,0,0,0)"] } : {}}
          transition={status === 'active' ? { repeat: Infinity, duration: 2 } : {}}
        >
          {status === 'complete' ? <Check className="w-6 h-6" /> : status === 'error' ? <X className="w-6 h-6" /> : <Icon className="w-6 h-6" />}
        </motion.div>
        
        <span className={`text-xs mt-3 font-medium text-center md:absolute md:top-16 md:w-32 md:-left-9 transition-colors ${status === 'active' ? 'text-foreground' : 'text-muted-foreground'}`}>
          {label}
        </span>
      </div>

      {!isLast && (
        <div className="h-10 w-0.5 md:h-0.5 md:w-16 lg:w-24 bg-stone-200 dark:bg-stone-800 my-2 md:my-0 md:mx-2 relative overflow-hidden self-center md:self-auto md:mb-5">
          <motion.div 
            className="absolute top-0 left-0 h-full md:w-full md:h-full bg-emerald-400 dark:bg-emerald-600"
            initial={status === 'complete' ? { scaleY: 1, scaleX: 1 } : { scaleY: 0, scaleX: 0 }}
            animate={status === 'complete' ? { scaleY: 1, scaleX: 1 } : { scaleY: 0, scaleX: 0 }}
            transition={{ duration: 0.5 }}
            style={{ transformOrigin: 'top left' }}
          />
        </div>
      )}
    </div>
  );
}
