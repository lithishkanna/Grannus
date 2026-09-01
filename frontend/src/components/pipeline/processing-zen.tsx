'use client';
import { motion } from 'framer-motion';

export function ProcessingZen({ text = "Processing..." }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-8 h-64 w-full max-w-sm mx-auto">
      <div className="relative w-32 h-32 flex items-center justify-center mb-8">
        {/* Animated Enso Circle */}
        <svg viewBox="0 0 100 100" className="w-full h-full rotate-90">
          <motion.path
            d="M 50, 50 m -40, 0 a 40,40 0 1,0 80,0 a 40,40 0 1,0 -80,0"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="text-primary/30"
            strokeDasharray="251.2"
            strokeDashoffset="0"
          />
          <motion.path
            d="M 50, 50 m -40, 0 a 40,40 0 1,0 80,0 a 40,40 0 1,0 -80,0"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            className="text-primary"
            initial={{ strokeDashoffset: 251.2 }}
            animate={{ strokeDashoffset: 0 }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            strokeDasharray="251.2"
          />
        </svg>
        
        {/* Center breathing pulse */}
        <motion.div 
          className="absolute w-12 h-12 bg-primary/20 rounded-full blur-md"
          animate={{ scale: [1, 1.5, 1], opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
      
      <motion.h3 
        className="font-heading text-xl text-foreground"
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      >
        {text}
      </motion.h3>
    </div>
  );
}
