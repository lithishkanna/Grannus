'use client';
import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { FileJson, Loader2, Download, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { exportFhirBundle, PipelineResult } from '@/lib/api';

interface FhirExportButtonProps {
  result: PipelineResult;
}

export function FhirExportButton({ result }: FhirExportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [exported, setExported] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    setError(null);
    try {
      const bundle = await exportFhirBundle(result);

      // Trigger download as JSON file
      const jsonStr = JSON.stringify(bundle, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/fhir+json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `grannus-fhir-${result.request_id.slice(0, 8)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setExported(true);
      setTimeout(() => setExported(false), 3000);
    } catch (err: any) {
      setError(err.message || 'FHIR export failed');
    } finally {
      setIsExporting(false);
    }
  }, [result]);

  return (
    <div className="space-y-1">
      <Button
        variant="outline"
        size="sm"
        onClick={handleExport}
        disabled={isExporting}
        className="w-full gap-2 border-border hover:bg-muted/50"
      >
        {isExporting ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Generating FHIR Bundle...
          </>
        ) : exported ? (
          <motion.span
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            className="flex items-center gap-2 text-emerald-600"
          >
            <CheckCircle className="w-4 h-4" />
            Exported!
          </motion.span>
        ) : (
          <>
            <FileJson className="w-4 h-4" />
            Export ABDM FHIR Bundle
            <Download className="w-3 h-3 ml-auto opacity-50" />
          </>
        )}
      </Button>
      {error && <p className="text-[10px] text-red-500 text-center">{error}</p>}
    </div>
  );
}
