'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AudioRecorder } from '@/components/voice/audio-recorder';
import { FileUploader } from '@/components/voice/file-uploader';
import { SUPPORTED_LANGUAGES, getActiveProfile, PatientProfile } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react';
import { ConsentDialog } from '@/components/voice/consent-dialog';

export default function VoiceInputPage() {
  const router = useRouter();
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [language, setLanguage] = useState('unknown');
  const [doctorLanguage, setDoctorLanguage] = useState('en-IN');
  const [activeProfile, setActiveProfileState] = useState<PatientProfile | null>(null);
  
  // DPDP Consent state
  const [showConsentModal, setShowConsentModal] = useState(false);
  const [consentApproved, setConsentApproved] = useState(false);

  // Optional context
  const [showContext, setShowContext] = useState(false);
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('');
  const [duration, setDuration] = useState('');
  const [conditions, setConditions] = useState('');
  const [medications, setMedications] = useState('');

  const [isClient, setIsClient] = useState(false);
  useEffect(() => {
    setIsClient(true);
    const profile = getActiveProfile();
    if (profile) {
      setActiveProfileState(profile);
      if (profile.preferred_language) setLanguage(profile.preferred_language);
      if (profile.age) setAge(String(profile.age));
      if (profile.gender) setGender(profile.gender);
      if (profile.known_conditions?.length) setConditions(profile.known_conditions.join(', '));
      if (profile.medications?.length) setMedications(profile.medications.join(', '));
    }
  }, []);

  const executePipelineSubmission = (blobToSubmit: Blob) => {
    const reader = new FileReader();
    reader.readAsDataURL(blobToSubmit);
    reader.onloadend = () => {
      const base64Audio = reader.result as string;
      const payload = {
        audio: base64Audio,
        language_code: language,
        doctor_preferred_language: doctorLanguage,
        age,
        gender,
        reported_duration: duration,
        known_conditions: conditions,
        current_medications: medications,
        profile_id: activeProfile?.id,
        dpdp_consent_verified: true,
      };
      
      sessionStorage.setItem('grannus_pipeline_payload', JSON.stringify(payload));
      router.push('/processing');
    };
  };

  const handleProcessClick = () => {
    if (!audioBlob) return;
    if (!consentApproved) {
      setShowConsentModal(true);
      return;
    }
    executePipelineSubmission(audioBlob);
  };

  const handleConsentAffirmed = () => {
    setConsentApproved(true);
    setShowConsentModal(false);
    if (audioBlob) {
      executePipelineSubmission(audioBlob);
    }
  };

  if (!isClient) return null; // Avoid hydration mismatch for tabs

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      <div className="text-center mb-10 animate-gentle-fade-in">
        <h1 className="text-4xl font-semibold text-foreground mb-3">Voice Input</h1>
        <p className="text-muted-foreground text-lg">Record or upload a patient consultation audio</p>
      </div>

      {activeProfile ? (
        <div className="mb-8 p-4 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-sm shadow-sm">
              {activeProfile.full_name.charAt(0).toUpperCase()}
            </div>
            <div>
              <p className="text-[11px] text-muted-foreground uppercase font-semibold tracking-wider">Active Patient Profile</p>
              <h3 className="text-base font-semibold text-foreground">
                {activeProfile.full_name}{' '}
                <span className="text-xs font-normal text-muted-foreground">
                  ({activeProfile.relation}{activeProfile.age ? `, ${activeProfile.age} yrs` : ''})
                </span>
              </h3>
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => router.push('/login')}
            className="text-xs rounded-xl h-8 font-medium"
          >
            Switch Profile
          </Button>
        </div>
      ) : (
        <div className="mb-8 p-3 bg-muted/60 border border-border rounded-2xl flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Consulting as Guest Patient (No profile selected)</span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => router.push('/login')}
            className="text-xs text-primary font-medium hover:underline h-7"
          >
            Sign In / Choose Family Member →
          </Button>
        </div>
      )}

      <div className="mb-12">
        <Tabs defaultValue="record" className="w-full">
          <TabsList className="grid w-full max-w-sm mx-auto grid-cols-2 mb-8 bg-card border border-border rounded-full p-1 h-12 shadow-sm">
            <TabsTrigger value="record" className="rounded-full text-base data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md transition-all">Record</TabsTrigger>
            <TabsTrigger value="upload" className="rounded-full text-base data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md transition-all">Upload</TabsTrigger>
          </TabsList>
          
          <TabsContent value="record" className="mt-0 focus-visible:outline-none focus-visible:ring-0">
            <AudioRecorder onAudioReady={setAudioBlob} />
          </TabsContent>
          <TabsContent value="upload" className="mt-0 focus-visible:outline-none focus-visible:ring-0">
            <FileUploader onAudioReady={setAudioBlob} />
          </TabsContent>
        </Tabs>
      </div>

      <div className="bg-card rounded-2xl p-6 md:p-8 shadow-ink-wash border border-border animate-gentle-fade-in" style={{ animationDelay: '0.2s' }}>
        <h2 className="text-xl font-heading font-medium text-foreground mb-6 pb-4 border-b border-border">Configuration</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="space-y-3">
            <Label className="text-sm font-medium text-foreground">Patient Language</Label>
            <Select value={language} onValueChange={(val) => setLanguage(val || 'unknown')}>
              <SelectTrigger className="w-full bg-background rounded-lg border-border h-11 focus:ring-primary">
                <SelectValue placeholder="Select language" />
              </SelectTrigger>
              <SelectContent>
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <SelectItem key={lang.code} value={lang.code}>
                    {lang.name} {lang.nativeName ? `(${lang.nativeName})` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <div className="space-y-3">
            <Label className="text-sm font-medium text-foreground">Doctor's Language</Label>
            <Select value={doctorLanguage} onValueChange={(val) => setDoctorLanguage(val || 'en-IN')}>
              <SelectTrigger className="w-full bg-background rounded-lg border-border h-11 focus:ring-primary">
                <SelectValue placeholder="Select language" />
              </SelectTrigger>
              <SelectContent>
                {SUPPORTED_LANGUAGES.filter(l => l.code !== 'unknown').map((lang) => (
                  <SelectItem key={lang.code} value={lang.code}>
                    {lang.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="border border-border rounded-xl overflow-hidden mb-8 bg-background/50">
          <button 
            onClick={() => setShowContext(!showContext)}
            className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors focus:outline-none"
          >
            <span className="font-medium text-foreground">Patient Context (Optional)</span>
            {showContext ? <ChevronUp className="w-5 h-5 text-muted-foreground" /> : <ChevronDown className="w-5 h-5 text-muted-foreground" />}
          </button>
          
          <AnimatePresence>
            {showContext && (
              <motion.div 
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="p-4 pt-0 border-t border-border grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2 mt-4">
                    <Label>Age</Label>
                    <Input type="number" placeholder="e.g. 45" value={age} onChange={e => setAge(e.target.value)} className="bg-background" />
                  </div>
                  <div className="space-y-2 mt-4">
                    <Label>Gender</Label>
                    <Select value={gender} onValueChange={(val) => setGender(val || '')}>
                      <SelectTrigger className="bg-background"><SelectValue placeholder="Select gender" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="male">Male</SelectItem>
                        <SelectItem value="female">Female</SelectItem>
                        <SelectItem value="other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label>Reported Duration</Label>
                    <Input placeholder="e.g. 3 days, since last week" value={duration} onChange={e => setDuration(e.target.value)} className="bg-background" />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label>Known Conditions</Label>
                    <Input placeholder="e.g. Type 2 Diabetes, Hypertension" value={conditions} onChange={e => setConditions(e.target.value)} className="bg-background" />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label>Current Medications</Label>
                    <Input placeholder="e.g. Metformin 500mg" value={medications} onChange={e => setMedications(e.target.value)} className="bg-background" />
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-border">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span>DPDP Act 2023 Compliant • 72h Audio Retention • 108/112 Emergency Referral</span>
          </div>

          <Button 
            size="lg" 
            className="w-full sm:w-auto px-10 h-12 rounded-full text-base font-medium shadow-md transition-transform active:scale-95"
            disabled={!audioBlob}
            onClick={handleProcessClick}
          >
            Process Audio
          </Button>
        </div>
      </div>

      <ConsentDialog
        isOpen={showConsentModal}
        selectedLanguage={language}
        onConsentGiven={handleConsentAffirmed}
        onConsentDenied={() => setShowConsentModal(false)}
      />
    </div>
  );
}
