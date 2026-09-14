'use client';
import { motion } from 'framer-motion';
import { Activity, Wind, Gauge, AudioWaveform } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { AcousticBiomarkerResult } from '@/lib/api';

const distressColors: Record<string, string> = {
  none: 'text-emerald-500',
  mild: 'text-amber-500',
  moderate: 'text-orange-500',
  severe: 'text-red-500',
};

const distressBg: Record<string, string> = {
  none: 'bg-emerald-500/10 border-emerald-500/20',
  mild: 'bg-amber-500/10 border-amber-500/20',
  moderate: 'bg-orange-500/10 border-orange-500/20',
  severe: 'bg-red-500/10 border-red-500/20',
};

export function AcousticBiomarkerCard({ data }: { data: AcousticBiomarkerResult }) {
  const level = data.distress_level || 'none';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Card className={`border ${distressBg[level]}`}>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base font-heading">
            <AudioWaveform className={`w-5 h-5 ${distressColors[level]}`} />
            Acoustic Biomarker Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Distress Level Badge */}
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm text-muted-foreground">Respiratory Distress</span>
            <span className={`text-sm font-semibold uppercase tracking-wider px-3 py-1 rounded-full border ${distressBg[level]} ${distressColors[level]}`}>
              {level}
            </span>
          </div>

          {/* Score Bar */}
          <div className="mb-5">
            <div className="flex justify-between text-xs text-muted-foreground mb-1">
              <span>Distress Score</span>
              <span>{(data.respiratory_distress_score * 100).toFixed(0)}%</span>
            </div>
            <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
              <motion.div
                className={`h-full rounded-full ${
                  level === 'severe' ? 'bg-red-500' :
                  level === 'moderate' ? 'bg-orange-500' :
                  level === 'mild' ? 'bg-amber-500' : 'bg-emerald-500'
                }`}
                initial={{ width: 0 }}
                animate={{ width: `${data.respiratory_distress_score * 100}%` }}
                transition={{ duration: 1, ease: 'easeOut' }}
              />
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col items-center p-3 rounded-lg bg-muted/40 border border-border">
              <Activity className="w-4 h-4 text-muted-foreground mb-1" />
              <span className="text-lg font-bold text-foreground">{data.cough_count}</span>
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Coughs</span>
            </div>
            <div className="flex flex-col items-center p-3 rounded-lg bg-muted/40 border border-border">
              <Wind className="w-4 h-4 text-muted-foreground mb-1" />
              <span className="text-lg font-bold text-foreground">{data.wheeze_detected ? 'Yes' : 'No'}</span>
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Wheeze</span>
            </div>
            <div className="flex flex-col items-center p-3 rounded-lg bg-muted/40 border border-border">
              <Gauge className="w-4 h-4 text-muted-foreground mb-1" />
              <span className="text-lg font-bold text-foreground">{data.breathlessness_pauses}</span>
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Pauses</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
