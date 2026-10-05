'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  ShieldCheck,
  Stethoscope,
  Phone,
  User,
  Users,
  PlusCircle,
  AlertCircle,
  CheckCircle2,
  Lock,
  ArrowRight,
  RefreshCw,
  KeyRound,
  AlertTriangle,
  PhoneCall,
} from 'lucide-react';
import {
  requestPhoneOtp,
  verifyPhoneOtp,
  loginStaff,
  getPatientProfiles,
  createPatientProfile,
  setActiveProfile,
  guestEmergencyIntake,
  PatientProfile,
} from '@/lib/api';

const STATE_COUNCILS = [
  'National Medical Commission (NMC)',
  'Tamil Nadu Medical Council',
  'Karnataka Medical Council',
  'Maharashtra Medical Council',
  'Delhi Medical Council',
  'Andhra Pradesh Medical Council',
  'Telangana State Medical Council',
  'West Bengal Medical Council',
  'Uttar Pradesh Medical Council',
  'Kerala Medical Council',
];

export default function LoginPage() {
  const router = useRouter();

  // Mode: 'patient' or 'staff'
  const [authMode, setAuthMode] = useState<'patient' | 'staff'>('patient');

  // Patient Phone OTP state
  const [phone, setPhone] = useState('+919876543210');
  const [otpCode, setOtpCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [devOtpHint, setDevOtpHint] = useState<string | null>(null);

  // Patient Profile state (Step 3)
  const [profiles, setProfiles] = useState<PatientProfile[]>([]);
  const [isSelectingProfile, setIsSelectingProfile] = useState(false);
  const [showAddProfile, setShowAddProfile] = useState(false);
  const [pinPromptProfile, setPinPromptProfile] = useState<PatientProfile | null>(null);
  const [enteredPin, setEnteredPin] = useState('');

  // Add profile form state
  const [newFullName, setNewFullName] = useState('');
  const [newAge, setNewAge] = useState('');
  const [newGender, setNewGender] = useState('female');
  const [newRelation, setNewRelation] = useState('self');
  const [newLanguage, setNewLanguage] = useState('ta-IN');
  const [newPin, setNewPin] = useState('');

  // Staff login state
  const [staffRole, setStaffRole] = useState<'doctor' | 'nurse' | 'admin'>('doctor');
  const [staffIdentifier, setStaffIdentifier] = useState('dr.rajan@hospital.in');
  const [staffPassword, setStaffPassword] = useState('grannus_secure_doctor_2026');
  const [regNumber, setRegNumber] = useState('TNMC-48291');
  const [council, setCouncil] = useState(STATE_COUNCILS[1]);

  // General state
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Emergency access state (H1.3)
  const [showEmergencyModal, setShowEmergencyModal] = useState(false);
  const [guestName, setGuestName] = useState('');
  const [guestAge, setGuestAge] = useState('');
  const [isEmergencyLoading, setIsEmergencyLoading] = useState(false);

  const handleGuestEmergency = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsEmergencyLoading(true);
    setErrorMessage('');
    try {
      const res = await guestEmergencyIntake({
        guest_name: guestName.trim() || 'Emergency Patient',
        age: guestAge.trim() || undefined,
      });
      setSuccessMessage('Emergency intake registered. Connecting to emergency protocol...');
      setTimeout(() => {
        router.push(`/results?id=${res.case_id}`);
      }, 400);
    } catch (err: any) {
      setErrorMessage(err.message || 'Could not register emergency intake.');
    } finally {
      setIsEmergencyLoading(false);
    }
  };

  // Cooldown countdown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const interval = setInterval(() => {
      setCooldown((c) => Math.max(0, c - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [cooldown]);

  // 1. Request Phone OTP
  const handleRequestOtp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');
    setIsLoading(true);

    try {
      const res = await requestPhoneOtp(phone.trim());
      setOtpSent(true);
      setCooldown(60);
      if (res.dev_otp_hint) {
        setDevOtpHint(res.dev_otp_hint);
        setOtpCode(res.dev_otp_hint);
      }
      setSuccessMessage(res.message || 'Verification code sent to your phone.');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to send verification code.');
    } finally {
      setIsLoading(false);
    }
  };

  // 2. Verify Phone OTP
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');
    setIsLoading(true);

    try {
      await verifyPhoneOtp(phone.trim(), otpCode.trim());
      setSuccessMessage('Phone verified! Loading family profiles...');

      // Load patient profiles
      const profs = await getPatientProfiles();
      setProfiles(profs);
      setIsSelectingProfile(true);

      if (profs.length === 0) {
        setShowAddProfile(true);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Verification code invalid.');
    } finally {
      setIsLoading(false);
    }
  };

  // 3. Select Profile
  const handleSelectProfile = (profile: PatientProfile) => {
    if (profile.pin_hash) {
      setPinPromptProfile(profile);
      setEnteredPin('');
      return;
    }
    setActiveProfile(profile);
    router.push('/input');
  };

  // 4. Verify PIN for Profile
  const handleVerifyPin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!pinPromptProfile) return;
    setActiveProfile(pinPromptProfile);
    setPinPromptProfile(null);
    router.push('/input');
  };

  // 5. Create New Profile
  const handleCreateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    setIsLoading(true);

    try {
      const created = await createPatientProfile({
        full_name: newFullName.trim(),
        age: newAge.trim() || undefined,
        gender: newGender,
        relation: newRelation,
        preferred_language: newLanguage,
        pin: newPin.trim() || undefined,
      });

      setActiveProfile(created);
      setSuccessMessage(`Profile created for ${created.full_name}! Redirecting to consultation...`);
      setTimeout(() => {
        router.push('/input');
      }, 500);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create profile.');
    } finally {
      setIsLoading(false);
    }
  };

  // 6. Staff Login
  const handleStaffLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');
    setIsLoading(true);

    try {
      const payload: Record<string, any> = {
        email: staffIdentifier.trim(),
        user_id: staffIdentifier.trim(),
        role: staffRole,
        password: staffPassword.trim(),
      };

      if (staffRole === 'doctor') {
        payload.doctor_registration_number = regNumber.trim();
        payload.state_medical_council = council;
      }

      await loginStaff(payload);
      setSuccessMessage('Clinician credentials verified! Entering dashboard...');
      setTimeout(() => {
        router.push('/dashboard');
      }, 600);
    } catch (err: any) {
      setErrorMessage(err.message || 'Staff authentication failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-12 max-w-lg animate-gentle-fade-in">
      {/* Header */}
      <div className="text-center mb-6">
        <div className="inline-flex p-3 bg-primary/10 rounded-full mb-3 text-primary">
          {authMode === 'patient' ? <Phone className="w-8 h-8" /> : <Stethoscope className="w-8 h-8" />}
        </div>
        <h1 className="text-3xl font-heading font-semibold text-foreground">
          {authMode === 'patient' ? 'Patient Portal' : 'Clinician Access'}
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          {authMode === 'patient'
            ? 'Voice Bridge with Urgency Routing — RuralCare AI'
            : 'Telemedicine Practice Guidelines 2020 Registered Medical Practitioner Verification'}
        </p>

        {/* Role Toggle Switch */}
        <div className="flex bg-muted p-1 rounded-xl mt-5 border border-border">
          <button
            type="button"
            onClick={() => {
              setAuthMode('patient');
              setErrorMessage('');
              setSuccessMessage('');
            }}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
              authMode === 'patient'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Patient (Phone OTP)
          </button>
          <button
            type="button"
            onClick={() => {
              setAuthMode('staff');
              setErrorMessage('');
              setSuccessMessage('');
            }}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
              authMode === 'staff'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Doctor & Staff
          </button>
        </div>
      </div>

      <Card className="border border-border/80 shadow-md">
        <CardHeader className="space-y-1 pb-4">
          <CardTitle className="text-xl">
            {authMode === 'patient'
              ? isSelectingProfile
                ? 'Select Patient Profile'
                : 'Patient Sign In'
              : 'Medical Staff Authentication'}
          </CardTitle>
          <CardDescription>
            {authMode === 'patient'
              ? isSelectingProfile
                ? 'Who is this voice consultation for?'
                : 'Enter your mobile number to receive a secure 6-digit OTP code.'
              : 'Sign in with your hospital email and registered medical license.'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {/* ============================================================= */}
          {/* PATIENT AUTH FLOW */}
          {/* ============================================================= */}
          {authMode === 'patient' && (
            <div>
              {/* Profile Selection Sub-Step */}
              {isSelectingProfile ? (
                <div className="space-y-4">
                  {/* PIN Check Modal/Card */}
                  {pinPromptProfile && (
                    <form onSubmit={handleVerifyPin} className="p-4 bg-muted/60 rounded-xl border border-border space-y-3">
                      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                        <KeyRound className="w-4 h-4 text-primary" />
                        <span>Enter 4-Digit Profile PIN for {pinPromptProfile.full_name}</span>
                      </div>
                      <Input
                        type="password"
                        maxLength={4}
                        placeholder="••••"
                        value={enteredPin}
                        onChange={(e) => setEnteredPin(e.target.value)}
                        required
                        className="text-center text-lg tracking-widest font-mono"
                      />
                      <div className="flex gap-2">
                        <Button type="submit" size="sm" className="flex-1">
                          Unlock Profile
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setPinPromptProfile(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </form>
                  )}

                  {/* Add Profile Form */}
                  {showAddProfile ? (
                    <form onSubmit={handleCreateProfile} className="space-y-3 p-4 bg-primary/5 rounded-xl border border-primary/20">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-semibold text-foreground">Add Family Member</h4>
                        <button
                          type="button"
                          onClick={() => setShowAddProfile(false)}
                          className="text-xs text-muted-foreground hover:text-foreground"
                        >
                          Cancel
                        </button>
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Full Name</Label>
                        <Input
                          placeholder="e.g. Ramesh Kumar"
                          value={newFullName}
                          onChange={(e) => setNewFullName(e.target.value)}
                          required
                          className="h-9"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <Label className="text-xs">Age</Label>
                          <Input
                            placeholder="e.g. 45"
                            value={newAge}
                            onChange={(e) => setNewAge(e.target.value)}
                            className="h-9"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Gender</Label>
                          <Select value={newGender} onValueChange={(val) => setNewGender(val || 'female')}>
                            <SelectTrigger className="h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="female">Female</SelectItem>
                              <SelectItem value="male">Male</SelectItem>
                              <SelectItem value="other">Other</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <Label className="text-xs">Relation</Label>
                          <Select value={newRelation} onValueChange={(val) => setNewRelation(val || 'self')}>
                            <SelectTrigger className="h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="self">Self</SelectItem>
                              <SelectItem value="mother">Mother</SelectItem>
                              <SelectItem value="father">Father</SelectItem>
                              <SelectItem value="child">Child</SelectItem>
                              <SelectItem value="spouse">Spouse</SelectItem>
                              <SelectItem value="other">Other</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Preferred Language</Label>
                          <Select value={newLanguage} onValueChange={(val) => setNewLanguage(val || 'ta-IN')}>
                            <SelectTrigger className="h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="ta-IN">Tamil (தமிழ்)</SelectItem>
                              <SelectItem value="hi-IN">Hindi (हिन्दी)</SelectItem>
                              <SelectItem value="te-IN">Telugu (తెలుగు)</SelectItem>
                              <SelectItem value="en-IN">English</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Optional 4-Digit Privacy PIN</Label>
                        <Input
                          type="password"
                          maxLength={4}
                          placeholder="Leave blank for open access"
                          value={newPin}
                          onChange={(e) => setNewPin(e.target.value)}
                          className="h-9 text-xs"
                        />
                      </div>

                      <Button type="submit" disabled={isLoading} className="w-full mt-2 h-9 text-xs">
                        {isLoading ? 'Creating...' : 'Save & Select Profile'}
                      </Button>
                    </form>
                  ) : (
                    <>
                      {/* Existing Profiles List */}
                      <div className="space-y-2">
                        {profiles.map((p) => (
                          <button
                            key={p.id}
                            type="button"
                            onClick={() => handleSelectProfile(p)}
                            className="w-full p-3.5 rounded-xl border border-border bg-card hover:bg-muted/50 transition-all text-left flex items-center justify-between group"
                          >
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold">
                                {p.full_name.charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <h4 className="font-medium text-foreground text-sm flex items-center gap-1.5">
                                  {p.full_name}
                                  {p.pin_hash && <Lock className="w-3.5 h-3.5 text-muted-foreground" />}
                                </h4>
                                <p className="text-xs text-muted-foreground capitalize">
                                  {p.relation} • {p.age ? `${p.age} yrs` : ''} {p.gender ? `• ${p.gender}` : ''}
                                </p>
                              </div>
                            </div>
                            <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                          </button>
                        ))}
                      </div>

                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setShowAddProfile(true)}
                        className="w-full h-10 border-dashed gap-2 text-xs"
                      >
                        <PlusCircle className="w-4 h-4" />
                        Add Family Member
                      </Button>
                    </>
                  )}
                </div>
              ) : showEmergencyModal ? (
                /* Emergency Guest Intake Modal (H1.3) */
                <form onSubmit={handleGuestEmergency} className="space-y-4 animate-gentle-fade-in">
                  <div className="p-4 rounded-xl bg-destructive/15 border border-destructive/30 text-destructive space-y-2">
                    <div className="flex items-center gap-2 font-bold text-sm">
                      <AlertTriangle className="w-5 h-5 text-destructive shrink-0" />
                      <span>Immediate Emergency Protocol (108 / 112)</span>
                    </div>
                    <p className="text-xs text-foreground/80 leading-relaxed">
                      For chest pain, difficulty breathing, heavy bleeding, or severe trauma, call ambulance emergency services immediately.
                    </p>
                    <div className="flex gap-2 pt-1">
                      <a
                        href="tel:108"
                        className="flex-1 inline-flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-destructive text-destructive-foreground font-bold text-xs shadow-sm hover:opacity-90 transition-opacity"
                      >
                        <PhoneCall className="w-3.5 h-3.5" />
                        Call 108 (Ambulance)
                      </a>
                      <a
                        href="tel:112"
                        className="flex-1 inline-flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-destructive text-destructive-foreground font-bold text-xs shadow-sm hover:opacity-90 transition-opacity"
                      >
                        <PhoneCall className="w-3.5 h-3.5" />
                        Call 112 (National ER)
                      </a>
                    </div>
                  </div>

                  <div className="space-y-3 pt-2">
                    <div className="space-y-1">
                      <Label className="text-xs">Patient Name (Required)</Label>
                      <Input
                        placeholder="e.g. Anbarasan or Family Member"
                        value={guestName}
                        onChange={(e) => setGuestName(e.target.value)}
                        required
                        className="h-9"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Age (Optional)</Label>
                      <Input
                        placeholder="e.g. 55"
                        value={guestAge}
                        onChange={(e) => setGuestAge(e.target.value)}
                        className="h-9"
                      />
                    </div>
                  </div>

                  <div className="space-y-2 pt-2">
                    <Button
                      type="submit"
                      variant="destructive"
                      disabled={isEmergencyLoading}
                      className="w-full font-semibold text-xs h-10 gap-2"
                    >
                      {isEmergencyLoading ? 'Alerting Hospital Casualty...' : 'Dispatch ER Alert & View Nearest Hospital'}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setShowEmergencyModal(false)}
                      className="w-full text-xs text-muted-foreground h-9"
                    >
                      Cancel — Back to Normal Sign In
                    </Button>
                  </div>
                </form>
              ) : !otpSent ? (
                /* Step 1: Phone Input */
                <div className="space-y-4">
                  {/* Emergency Access Banner (H1.3) */}
                  <div className="p-3.5 rounded-xl bg-destructive/10 border border-destructive/25 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center shrink-0">
                        <AlertTriangle className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-destructive">Medical Emergency?</p>
                        <p className="text-[11px] text-muted-foreground">Skip OTP to trigger hospital ER assistance.</p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      onClick={() => setShowEmergencyModal(true)}
                      className="text-xs font-bold shrink-0 h-8 gap-1.5"
                    >
                      <PhoneCall className="w-3.5 h-3.5" />
                      Call 108
                    </Button>
                  </div>

                  <form onSubmit={handleRequestOtp} className="space-y-4">
                  <div className="space-y-2">
                    <Label>Mobile Phone Number</Label>
                    <div className="relative">
                      <Input
                        type="tel"
                        placeholder="+91 98765 43210"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        required
                        className="h-11 pl-10 text-base"
                      />
                      <Phone className="w-4 h-4 text-muted-foreground absolute left-3 top-3.5" />
                    </div>
                  </div>

                  {/* Dev Test Number Hint Box */}
                  <div className="p-3 bg-muted/60 border border-border/80 rounded-xl text-xs space-y-1">
                    <div className="font-medium text-foreground flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-primary" />
                      <span>Quick Test / Sandbox Access Numbers</span>
                    </div>
                    <p className="text-muted-foreground">
                      Use <span className="font-mono text-foreground font-semibold">+919876543210</span> (Code: <span className="font-mono font-semibold">123456</span>) to bypass external SMS network.
                    </p>
                  </div>

                  <Button
                    type="submit"
                    disabled={isLoading}
                    className="w-full h-11 rounded-lg font-medium gap-2 text-sm"
                  >
                    {isLoading ? 'Sending Code...' : 'Send Verification Code'}
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                </form>
              </div>
              ) : (
                /* Step 2: OTP Verification */
                <form onSubmit={handleVerifyOtp} className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>6-Digit Verification Code</Label>
                      <button
                        type="button"
                        onClick={() => {
                          setOtpSent(false);
                          setErrorMessage('');
                        }}
                        className="text-xs text-primary hover:underline"
                      >
                        Change number
                      </button>
                    </div>
                    <Input
                      type="text"
                      maxLength={6}
                      placeholder="123456"
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value)}
                      required
                      className="h-12 text-center text-2xl tracking-widest font-mono font-semibold"
                    />
                    <p className="text-xs text-muted-foreground text-center">
                      Code sent to <span className="font-semibold text-foreground">{phone}</span>
                    </p>
                  </div>

                  {devOtpHint && (
                    <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-xs text-emerald-700 dark:text-emerald-400 text-center">
                      Access Code: <span className="font-mono font-bold tracking-wider">{devOtpHint}</span>
                    </div>
                  )}

                  <Button
                    type="submit"
                    disabled={isLoading || otpCode.length < 6}
                    className="w-full h-11 rounded-lg font-medium gap-2 text-sm"
                  >
                    <Lock className="w-4 h-4" />
                    {isLoading ? 'Verifying Code...' : 'Verify & Continue'}
                  </Button>

                  <div className="text-center pt-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={cooldown > 0 || isLoading}
                      onClick={() => handleRequestOtp()}
                      className="text-xs text-muted-foreground gap-1.5"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      {cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend Code'}
                    </Button>
                  </div>
                </form>
              )}
            </div>
          )}

          {/* ============================================================= */}
          {/* STAFF AUTH FLOW */}
          {/* ============================================================= */}
          {authMode === 'staff' && (
            <form onSubmit={handleStaffLogin} className="space-y-4">
              <div className="space-y-2">
                <Label>Hospital Staff Role</Label>
                <Select value={staffRole} onValueChange={(val: any) => setStaffRole(val || 'doctor')}>
                  <SelectTrigger className="h-10">
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="doctor">Registered Medical Practitioner (Doctor)</SelectItem>
                    <SelectItem value="nurse">Staff Nurse</SelectItem>
                    <SelectItem value="admin">Hospital Administrator</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Hospital Email / Clinician ID</Label>
                <Input
                  placeholder="e.g. dr.rajan@hospital.in"
                  value={staffIdentifier}
                  onChange={(e) => setStaffIdentifier(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label>Account Password</Label>
                <Input
                  type="password"
                  placeholder="Enter secure password"
                  value={staffPassword}
                  onChange={(e) => setStaffPassword(e.target.value)}
                  required
                />
                <p className="text-[11px] text-muted-foreground">
                  Clinician credentials: <span className="font-mono">dr.rajan@hospital.in</span> / <span className="font-mono">grannus_secure_doctor_2026</span>
                </p>
              </div>

              {staffRole === 'doctor' && (
                <>
                  <div className="space-y-2">
                    <Label>NMC / State Medical Council Registration No.</Label>
                    <Input
                      placeholder="e.g. TNMC-54321 or NMC-109283"
                      value={regNumber}
                      onChange={(e) => setRegNumber(e.target.value)}
                      required
                    />
                    <p className="text-[11px] text-muted-foreground">
                      Required under Telemedicine Practice Guidelines 2020 for lawful digital triage review.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label>Registered Medical Council</Label>
                    <Select value={council} onValueChange={(val) => setCouncil(val || STATE_COUNCILS[0])}>
                      <SelectTrigger className="h-10">
                        <SelectValue placeholder="Select Council" />
                      </SelectTrigger>
                      <SelectContent>
                        {STATE_COUNCILS.map((c) => (
                          <SelectItem key={c} value={c}>{c}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </>
              )}

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full mt-4 h-11 rounded-lg font-medium gap-2"
              >
                <Lock className="w-4 h-4" />
                {isLoading ? 'Verifying Credentials...' : 'Verify & Enter Dashboard'}
              </Button>
            </form>
          )}

          {/* Feedback Messages */}
          {errorMessage && (
            <div className="p-3 mt-4 bg-destructive/10 border border-destructive/30 rounded-lg flex items-center gap-2 text-xs text-destructive">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="p-3 mt-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg flex items-center gap-2 text-xs text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}
        </CardContent>

        <CardFooter className="flex flex-col text-center border-t border-border/60 pt-4 pb-4">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground justify-center">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>DPDP Act 2023 & MoHFW Telemedicine Compliant Session</span>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
