'use client';
import { motion } from 'framer-motion';

export function PriorityFilter({ selected, onChange }: { selected: string, onChange: (val: string) => void }) {
  const filters = [
    { id: 'All', label: 'All', color: 'bg-primary' },
    { id: 'HIGH', label: 'High', color: 'bg-[#a65d57]' },
    { id: 'MEDIUM', label: 'Medium', color: 'bg-[#c49a3c]' },
    { id: 'LOW', label: 'Low', color: 'bg-[#5a7247]' },
  ];

  return (
    <div className="flex flex-wrap gap-2 mb-6">
      {filters.map((f) => {
        const isActive = selected === f.id;
        return (
          <button
            key={f.id}
            onClick={() => onChange(f.id)}
            className={`relative px-4 py-2 rounded-full text-sm font-medium transition-colors ${isActive ? 'text-foreground' : 'text-muted-foreground hover:bg-muted'}`}
          >
            {isActive && (
              <motion.div
                layoutId="active-filter"
                className="absolute inset-0 bg-muted rounded-full -z-10 border border-border"
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              />
            )}
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${f.color}`} />
              {f.label}
            </div>
          </button>
        );
      })}
    </div>
  );
}
