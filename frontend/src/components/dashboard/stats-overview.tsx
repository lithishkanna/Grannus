'use client';
import { motion } from 'framer-motion';
import { Activity, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

export function StatsOverview({ consultations }: { consultations: any[] }) {
  const total = consultations.length;
  const high = consultations.filter(c => c.result?.priority?.level === 'HIGH').length;
  const medium = consultations.filter(c => c.result?.priority?.level === 'MEDIUM').length;
  const low = consultations.filter(c => c.result?.priority?.level === 'LOW').length;

  const stats = [
    { label: 'Total Consultations', value: total, icon: Activity, color: 'text-primary' },
    { label: 'High Priority', value: high, icon: AlertTriangle, color: 'text-[#a65d57]' },
    { label: 'Medium Priority', value: medium, icon: AlertCircle, color: 'text-[#c49a3c]' },
    { label: 'Low Priority', value: low, icon: CheckCircle, color: 'text-[#5a7247]' },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {stats.map((stat, idx) => {
        const Icon = stat.icon;
        return (
          <motion.div 
            key={idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
          >
            <Card className="rounded-organic-1 shadow-sm hover:shadow-md transition-shadow border-border">
              <CardContent className="p-6 flex flex-col items-center text-center">
                <Icon className={`w-8 h-8 mb-4 ${stat.color}`} />
                <h3 className="text-3xl font-heading font-medium text-foreground mb-1">{stat.value}</h3>
                <p className="text-sm text-muted-foreground font-medium uppercase tracking-wider">{stat.label}</p>
              </CardContent>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}
