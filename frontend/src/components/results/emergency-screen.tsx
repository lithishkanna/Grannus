'use client';

import React from 'react';
import { PhoneCall, AlertTriangle, ShieldAlert, HeartPulse, MapPin } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface EmergencyScreenProps {
  reasons?: string[];
  emergencyNumbers?: string[];
}

export function EmergencyScreen({
  reasons = ['Critical clinical safety red flag detected'],
  emergencyNumbers = ['108', '112'],
}: EmergencyScreenProps) {
  return (
    <div className="w-full bg-destructive/10 border-2 border-destructive rounded-2xl p-6 sm:p-8 shadow-lg mb-8 animate-pulse-gentle">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 pb-6 border-b border-destructive/20">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-destructive text-white flex items-center justify-center shrink-0 shadow-md">
            <ShieldAlert className="w-8 h-8 animate-bounce" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold tracking-wide uppercase bg-destructive text-white">
                Emergency Alert — Immediate Care Needed
              </span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-destructive mt-1">
              Call Emergency Medical Services Now
            </h2>
            <p className="text-sm text-foreground/80 mt-1">
              Do not wait. This consultation exhibits critical symptoms requiring urgent in-person medical evaluation.
            </p>
          </div>
        </div>

        {/* Big Tap to Call Buttons */}
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <a
            href="tel:108"
            className="flex-1 md:flex-none inline-flex items-center justify-center gap-2 px-6 py-4 rounded-xl bg-destructive text-white text-lg font-bold shadow-md hover:bg-destructive/90 transition-all active:scale-95"
          >
            <PhoneCall className="w-6 h-6" />
            <span>Call 108 (Ambulance)</span>
          </a>
          <a
            href="tel:112"
            className="flex-1 md:flex-none inline-flex items-center justify-center gap-2 px-6 py-4 rounded-xl bg-secondary text-secondary-foreground text-lg font-bold border border-border shadow-sm hover:bg-secondary/80 transition-all active:scale-95"
          >
            <PhoneCall className="w-5 h-5 text-destructive" />
            <span>Call 112 (Emergency)</span>
          </a>
        </div>
      </div>

      {/* Trigger Reasons */}
      {reasons && reasons.length > 0 && (
        <div className="mt-5 p-4 rounded-xl bg-card border border-destructive/20">
          <div className="text-xs font-semibold uppercase tracking-wider text-destructive flex items-center gap-1.5 mb-2">
            <AlertTriangle className="w-4 h-4" />
            Triggered Emergency Indicators:
          </div>
          <ul className="list-disc list-inside space-y-1 text-sm text-foreground/90">
            {reasons.map((r, i) => (
              <li key={i} className="font-medium text-destructive-foreground/90">
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Immediate Stabilisation & First Aid Advice */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mt-6">
        <div className="bg-card p-4 rounded-xl border border-border shadow-sm">
          <div className="flex items-center gap-2 font-semibold text-foreground text-sm mb-1.5">
            <HeartPulse className="w-4 h-4 text-destructive" />
            Rest & Positioning
          </div>
          <p className="text-xs text-muted-foreground">
            Keep patient seated or resting in a semi-upright posture. Loosen any tight clothing around collar, chest, or waist.
          </p>
        </div>

        <div className="bg-card p-4 rounded-xl border border-border shadow-sm">
          <div className="flex items-center gap-2 font-semibold text-foreground text-sm mb-1.5">
            <AlertTriangle className="w-4 h-4 text-destructive" />
            Airway & Breathing
          </div>
          <p className="text-xs text-muted-foreground">
            Ensure fresh airflow. Do NOT give oral liquids or medications if patient is struggling to breathe or drowsy.
          </p>
        </div>

        <div className="bg-card p-4 rounded-xl border border-border shadow-sm">
          <div className="flex items-center gap-2 font-semibold text-foreground text-sm mb-1.5">
            <MapPin className="w-4 h-4 text-destructive" />
            Primary Care Escalation
          </div>
          <p className="text-xs text-muted-foreground">
            If ambulance transport is delayed, arrange private or community vehicle to the nearest PHC, CHC, or District Hospital immediately.
          </p>
        </div>
      </div>
    </div>
  );
}
