'use client';
import { SafetyRedFlag } from '@/lib/api';
import { AlertTriangle, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { Badge } from '@/components/ui/badge';

export function SafetyFlags({ flags, hasCritical }: { flags: SafetyRedFlag[], hasCritical: boolean }) {
  if (!flags || flags.length === 0) return null;

  return (
    <div className={`rounded-xl p-5 border ${hasCritical ? 'bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-900/50' : 'bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-900/50'}`}>
      <div className="flex items-center gap-3 mb-4">
        {hasCritical ? (
          <AlertTriangle className="w-6 h-6 text-red-600 dark:text-red-400" />
        ) : (
          <AlertCircle className="w-6 h-6 text-amber-600 dark:text-amber-400" />
        )}
        <h3 className={`font-heading text-xl font-medium ${hasCritical ? 'text-red-800 dark:text-red-400' : 'text-amber-800 dark:text-amber-400'}`}>
          Safety Red Flags Detected
        </h3>
      </div>

      <div className="space-y-4">
        {flags.map((flag, idx) => (
          <motion.div 
            key={idx}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.1 }}
            className={`p-4 rounded-lg bg-background shadow-sm border ${flag.severity === 'critical' ? 'border-red-200 dark:border-red-800/50' : 'border-amber-200 dark:border-amber-800/50'}`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mb-2">
              <span className="font-semibold text-foreground">{flag.symptom}</span>
              <Badge variant="outline" className={flag.severity === 'critical' ? 'bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400' : 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400'}>
                {flag.severity}
              </Badge>
            </div>
            <p className="text-sm text-foreground/80 mb-2">{flag.reason}</p>
            <div className="text-sm font-medium p-2 rounded bg-muted/50 text-foreground">
              <span className="opacity-70 mr-2">Action:</span>
              {flag.action}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
