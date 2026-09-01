'use client';
import { PIPELINE_STAGES } from '@/hooks/use-pipeline';
import { StageIndicator, StageStatus } from './stage-indicator';
import { Progress } from '@/components/ui/progress';

interface PipelineFlowProps {
  currentStage: string | null;
  stageProgress: Record<string, StageStatus>;
}

export function PipelineFlow({ currentStage, stageProgress }: PipelineFlowProps) {
  const activeCount = Object.values(stageProgress).filter(s => s === 'complete').length;
  const progressPercent = PIPELINE_STAGES.length > 0 ? (activeCount / PIPELINE_STAGES.length) * 100 : 0;

  return (
    <div className="w-full max-w-4xl mx-auto p-6 md:p-12 bg-card rounded-organic-1 shadow-ink-wash border border-border">
      <div className="mb-12 flex flex-col items-center">
        <div className="flex justify-between w-full mb-2 text-sm font-medium text-muted-foreground">
          <span>Processing Pipeline</span>
          <span>{Math.round(progressPercent)}%</span>
        </div>
        <Progress value={progressPercent} className="h-2 w-full bg-muted" />
      </div>

      <div className="flex flex-col md:flex-row items-center justify-between gap-2 md:gap-0 mt-8 mb-10">
        {PIPELINE_STAGES.map((stage, idx) => (
          <StageIndicator 
            key={stage.id}
            label={stage.label}
            iconName={stage.icon as any}
            status={stageProgress[stage.id] || 'pending'}
            isLast={idx === PIPELINE_STAGES.length - 1}
          />
        ))}
      </div>
    </div>
  );
}
