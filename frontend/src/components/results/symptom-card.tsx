'use client';
import { Symptom } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { motion } from 'framer-motion';

export function SymptomCard({ symptom }: { symptom: Symptom }) {
  const getSeverityColor = (severity: string | null) => {
    switch (severity) {
      case 'unbearable':
      case 'severe': return 'bg-destructive/10 text-destructive border-destructive/20 hover:bg-destructive/20';
      case 'moderate': return 'bg-amber-100 text-amber-700 border-amber-200 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-700';
      case 'mild':
      case 'slight': return 'bg-primary/10 text-primary border-primary/20 hover:bg-primary/20';
      default: return 'bg-muted text-muted-foreground';
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-4 rounded-organic-2 border bg-card shadow-sm transition-shadow hover:shadow-md ${symptom.negated ? 'opacity-70 grayscale' : 'border-border'}`}
    >
      <div className="flex justify-between items-start mb-2">
        <h4 className={`font-medium text-lg ${symptom.negated ? 'line-through text-muted-foreground' : 'text-foreground'}`}>
          {symptom.name}
        </h4>
        {symptom.negated && <Badge variant="outline" className="bg-muted text-muted-foreground ml-2">Denied</Badge>}
      </div>

      <div className="flex flex-wrap gap-2 mt-3">
        {symptom.severity && !symptom.negated && (
          <Badge variant="outline" className={getSeverityColor(symptom.severity)}>
            {symptom.severity}
          </Badge>
        )}
        
        {symptom.duration?.value && (
          <Badge variant="secondary" className="bg-secondary/50 font-normal">
            {symptom.duration.value} {symptom.duration.unit}
          </Badge>
        )}
        
        {symptom.frequency && (
          <Badge variant="secondary" className="bg-secondary/50 font-normal">
            {symptom.frequency}
          </Badge>
        )}
        
        {symptom.body_location && (
          <Badge variant="secondary" className="bg-secondary/50 font-normal">
            {symptom.body_location}
          </Badge>
        )}
      </div>
      
      {symptom.confidence < 0.7 && (
        <div className="mt-3 text-xs text-muted-foreground italic opacity-70">
          Low confidence extraction ({Math.round(symptom.confidence * 100)}%)
        </div>
      )}
    </motion.div>
  );
}
