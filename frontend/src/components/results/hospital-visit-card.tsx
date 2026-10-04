'use client';

import React from 'react';
import { MapPin, Phone, Clock, Navigation, Building2, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface HospitalVisitCardProps {
  hospitalName?: string;
  departmentName?: string;
  address?: string;
  emergencyPhone?: string;
  hours?: string;
  mapQuery?: string;
}

export function HospitalVisitCard({
  hospitalName = 'District Hospital Rural Outreach',
  departmentName,
  address = 'Main Hospital Road, Taluk Headquarters, Tamil Nadu, India',
  emergencyPhone = '108',
  hours = '24/7 Emergency & Casualty | OPD: Mon–Sat 8:00 AM – 2:00 PM',
  mapQuery = 'District Hospital Tamil Nadu',
}: HospitalVisitCardProps) {
  const mapUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
    mapQuery || hospitalName
  )}`;

  return (
    <div className="bg-card border border-border rounded-2xl p-6 md:p-8 shadow-sm transition-all hover:border-primary/40">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-5 border-b border-border/60">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                Hospital Visit Information
              </span>
              {departmentName && (
                <span className="text-[11px] font-semibold text-muted-foreground">
                  • {departmentName}
                </span>
              )}
            </div>
            <h3 className="text-xl font-heading font-semibold text-foreground mt-1">
              {hospitalName}
            </h3>
          </div>
        </div>

        <a
          href={mapUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground text-xs font-semibold shadow-sm hover:bg-primary/90 transition-all active:scale-95"
        >
          <Navigation className="w-4 h-4" />
          <span>Open in Google Maps</span>
          <ExternalLink className="w-3.5 h-3.5 opacity-80" />
        </a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6">
        {/* Address */}
        <div className="flex items-start gap-3">
          <MapPin className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Location & Address
            </h4>
            <p className="text-sm text-foreground/90 leading-relaxed">{address}</p>
            <span className="text-xs text-muted-foreground mt-1 block">
              Free government ambulance drop point at Gate 1
            </span>
          </div>
        </div>

        {/* Operating Hours */}
        <div className="flex items-start gap-3">
          <Clock className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Operating Hours
            </h4>
            <p className="text-sm text-foreground/90 leading-relaxed">{hours}</p>
            <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium mt-1 block">
              Emergency Ward is open 24 hours every day
            </span>
          </div>
        </div>

        {/* Contact numbers */}
        <div className="flex items-start gap-3">
          <Phone className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Emergency & Inquiries
            </h4>
            <div className="space-y-1">
              <a
                href="tel:108"
                className="text-sm font-bold text-destructive hover:underline flex items-center gap-1.5"
              >
                <span>Call 108 (National Ambulance)</span>
              </a>
              <a
                href="tel:112"
                className="text-xs text-foreground/80 hover:underline block"
              >
                112 (Unified Police & Medical Dispatch)
              </a>
              <span className="text-xs text-muted-foreground block">
                Hospital Desk: +91 44 2400 1234
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
