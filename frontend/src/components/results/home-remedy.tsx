'use client';
import { HomeRemedyGuidance } from '@/lib/api';
import { Heart, Activity, AlertTriangle, Info } from 'lucide-react';

export function HomeRemedy({ data }: { data: HomeRemedyGuidance }) {
  const isTranslated = !!data.translated_care_steps;
  const careSteps = data.translated_care_steps || data.care_steps.map(s => s.step);
  const seekDoctor = data.translated_seek_doctor_if || data.seek_doctor_if;

  return (
    <div className="bg-[#f2f6eb] dark:bg-[#1f2618] rounded-2xl p-6 md:p-8 border border-[#e1e9d3] dark:border-[#38422c] shadow-sm">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8 pb-4 border-b border-[#e1e9d3] dark:border-[#38422c]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#5a7247] rounded-full flex items-center justify-center text-white">
            <Heart className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-heading text-xl font-medium text-[#38422c] dark:text-[#e1e9d3]">Home Care Guidance</h3>
            <p className="text-sm text-[#6c7d5c] dark:text-[#a3b392]">Safe, immediate relief steps</p>
          </div>
        </div>
      </div>

      <div className="space-y-8 text-[#4a5839] dark:text-[#cbd4be]">
        <div>
          <h4 className="flex items-center gap-2 font-medium text-lg mb-4 text-[#38422c] dark:text-[#f4f7f0]">
            <Activity className="w-5 h-5 text-[#5a7247]" />
            Care Steps
          </h4>
          <ol className="space-y-4 pl-2">
            {careSteps.map((step, idx) => (
              <li key={idx} className="flex gap-4">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[#5a7247]/20 text-[#5a7247] flex items-center justify-center text-sm font-semibold mt-0.5">
                  {idx + 1}
                </span>
                <span className="leading-relaxed">{step}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="p-5 bg-red-50 dark:bg-red-950/30 rounded-xl border border-red-100 dark:border-red-900/50 text-red-800 dark:text-red-300">
          <h4 className="flex items-center gap-2 font-medium mb-3 text-red-900 dark:text-red-400">
            <AlertTriangle className="w-5 h-5" />
            Seek a doctor immediately if:
          </h4>
          <ul className="list-disc pl-5 space-y-2">
            {seekDoctor.map((condition, idx) => (
              <li key={idx}>{condition}</li>
            ))}
          </ul>
        </div>

        <div className="flex items-start gap-3 p-4 bg-white/50 dark:bg-black/20 rounded-lg text-sm text-[#6c7d5c] dark:text-[#8b9e78]">
          <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <p>{data.disclaimer}</p>
        </div>
      </div>
    </div>
  );
}
