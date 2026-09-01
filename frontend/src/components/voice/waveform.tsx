'use client';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

export function Waveform({ isRecording, isPlaying }: { isRecording: boolean; isPlaying: boolean }) {
  const [bars, setBars] = useState<number[]>(Array(40).fill(10));

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isRecording || isPlaying) {
      interval = setInterval(() => {
        setBars(prev => prev.map(() => Math.floor(Math.random() * 80) + 10));
      }, 100);
    } else {
      setBars(Array(40).fill(10));
    }
    return () => clearInterval(interval);
  }, [isRecording, isPlaying]);

  return (
    <div className="flex items-center justify-center h-24 gap-1 w-full max-w-md mx-auto">
      {bars.map((height, i) => (
        <motion.div
          key={i}
          className="w-1.5 bg-primary/60 rounded-full"
          animate={{ height: `${height}%` }}
          transition={{ type: 'tween', duration: 0.1 }}
        />
      ))}
    </div>
  );
}
