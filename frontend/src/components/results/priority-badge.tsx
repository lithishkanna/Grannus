'use client';
import { motion } from 'framer-motion';

export function PriorityBadge({ level, confidence, size = 'md' }: { level: string; confidence?: number; size?: 'sm' | 'md' | 'lg' }) {
  const getStyles = () => {
    switch (level) {
      case 'HIGH': return 'bg-[#a65d57] text-white shadow-[0_0_15px_rgba(166,93,87,0.4)]';
      case 'MEDIUM': return 'bg-[#c49a3c] text-white shadow-[0_0_15px_rgba(196,154,60,0.4)]';
      case 'LOW': return 'bg-[#5a7247] text-white shadow-[0_0_15px_rgba(90,114,71,0.4)]';
      case 'PENDING_REVIEW': return 'bg-[#5b6b7a] text-white shadow-[0_0_15px_rgba(91,107,122,0.4)]';
      default: return 'bg-stone-300 text-stone-800';
    }
  };

  const getSize = () => {
    switch (size) {
      case 'sm': return 'text-xs px-2 py-0.5';
      case 'lg': return 'text-lg px-6 py-2';
      default: return 'text-sm px-4 py-1';
    }
  };

  return (
    <motion.div 
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={`inline-flex items-center gap-2 rounded-full font-medium tracking-wide ${getStyles()} ${getSize()}`}
    >
      <span>{level.replace('_', ' ')}</span>
      {confidence !== undefined && (
        <span className="opacity-80 text-[0.85em] ml-1 border-l border-white/30 pl-2">
          {Math.round(confidence * 100)}%
        </span>
      )}
    </motion.div>
  );
}
