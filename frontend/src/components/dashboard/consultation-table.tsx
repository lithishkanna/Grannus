'use client';
import { formatDistanceToNow } from 'date-fns';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { PriorityBadge } from '@/components/results/priority-badge';

export function ConsultationTable({ consultations, onSelect }: { consultations: any[], onSelect: (c: any) => void }) {
  if (consultations.length === 0) {
    return (
      <div className="bg-card border border-border rounded-xl p-12 text-center text-muted-foreground shadow-sm">
        No consultations found matching your criteria.
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden animate-gentle-fade-in">
      <Table>
        <TableHeader className="bg-muted/30">
          <TableRow className="border-border">
            <TableHead className="w-[150px]">Time</TableHead>
            <TableHead>Language</TableHead>
            <TableHead className="hidden md:table-cell">Chief Complaint</TableHead>
            <TableHead>Priority</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {consultations.map((c) => (
            <TableRow 
              key={c.id} 
              className="cursor-pointer hover:bg-muted/30 transition-colors border-border"
              onClick={() => onSelect(c)}
            >
              <TableCell className="text-muted-foreground whitespace-nowrap">
                {c.created_at ? formatDistanceToNow(new Date(c.created_at), { addSuffix: true }) : 'Unknown'}
              </TableCell>
              <TableCell className="font-medium">
                {c.result?.patient_input?.language || 'Unknown'}
              </TableCell>
              <TableCell className="hidden md:table-cell text-muted-foreground truncate max-w-[300px]">
                {c.result?.clinical_summary?.chief_complaint || 'N/A'}
              </TableCell>
              <TableCell>
                {c.result?.priority?.level ? (
                  <PriorityBadge level={c.result.priority.level} size="sm" />
                ) : (
                  <span className="text-muted-foreground">Unknown</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
