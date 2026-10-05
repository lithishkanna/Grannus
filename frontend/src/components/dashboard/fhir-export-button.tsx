'use client';
import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { FileJson, Loader2, Download, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { exportFhirBundle, loginAsClinician, PipelineResult } from '@/lib/api';

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

  const handleQuickLoginAndExport = async () => {
    setIsExporting(true);
    setError(null);
    try {
      await loginAsClinician();
      await handleExport();
    } catch (err: any) {
      setError('Clinician login failed. Please sign in via the Clinician Portal.');
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-1.5">
      <Button
        variant="outline"
        size="sm"
        onClick={handleExport}
        disabled={isExporting}
        className="w-full gap-2 border-border hover:bg-muted/50 text-xs"
      >
        {isExporting ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
            Generating FHIR Bundle...
          </>
        ) : exported ? (
          <motion.span
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            className="flex items-center gap-2 text-emerald-600 font-medium"
          >
            <CheckCircle className="w-4 h-4" />
            FHIR Bundle Exported!
          </motion.span>
        ) : (
          <>
            <FileJson className="w-4 h-4 text-primary" />
            Export ABDM FHIR Bundle
            <Download className="w-3 h-3 ml-auto opacity-50" />
          </>
        )}
      </Button>
      {error && (
        <div className="p-2 rounded-lg bg-destructive/10 border border-destructive/20 text-center">
          <p className="text-[11px] text-destructive leading-tight">{error}</p>
          {(error.includes('login') || error.includes('authorized') || error.includes('401')) && (
            <button
              type="button"
              onClick={handleQuickLoginAndExport}
              disabled={isExporting}
              className="mt-1.5 text-[10px] text-primary underline font-semibold hover:text-primary/80 block w-full text-center"
            >
              Sign In as Dr. Rajan K., MD (TNMC-48291) & Download
            </button>
          )}
        </div>
      )}
    </div>
  );
}
