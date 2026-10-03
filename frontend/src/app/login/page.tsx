'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ShieldCheck, Stethoscope, AlertCircle, CheckCircle2, Lock } from 'lucide-react';

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
  const [role, setRole] = useState<'doctor' | 'asha_worker' | 'admin'>('doctor');
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [regNumber, setRegNumber] = useState('');
  const [council, setCouncil] = useState(STATE_COUNCILS[0]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');
    setIsLoading(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const payload: Record<string, any> = {
        user_id: userId.trim() || (role === 'doctor' ? 'dr_clinician' : 'admin_user'),
        role: role,
        password: password.trim() || (role === 'doctor' ? 'grannus_secure_doctor_2026' : 'grannus_secure_admin_2026'),
      };

      if (role === 'doctor') {
        payload.doctor_registration_number = regNumber.trim();
        payload.state_medical_council = council;
      }

      const res = await fetch(`${apiUrl}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Authentication failed. Please verify credentials.');
      }

      const data = await res.json();
      localStorage.setItem('grannus_auth_token', data.token);
      localStorage.setItem('grannus_user', JSON.stringify({
        user_id: data.user_id,
        role: data.role,
        is_verified_doctor: data.is_verified_doctor,
        doctor_registration_number: data.doctor_registration_number,
      }));

      setSuccessMessage('Credentials verified successfully! Redirecting...');
      setTimeout(() => {
        router.push('/dashboard');
      }, 800);
    } catch (err: any) {
      setErrorMessage(err.message || 'Verification error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-16 max-w-lg animate-gentle-fade-in">
      <div className="text-center mb-8">
        <div className="inline-flex p-3 bg-primary/10 rounded-full mb-3 text-primary">
          <Stethoscope className="w-8 h-8" />
        </div>
        <h1 className="text-3xl font-heading font-semibold text-foreground">Clinician Access</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Telemedicine Practice Guidelines 2020 Registered Medical Practitioner Verification
        </p>
      </div>

      <Card className="border border-border/80 shadow-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-xl">Authentication Portal</CardTitle>
          <CardDescription>
            Enter your official registration details to review triage cases & sign prescriptions.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Label>Access Role</Label>
              <Select value={role} onValueChange={(val) => setRole((val as any) || 'doctor')}>
                <SelectTrigger className="h-10">
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="doctor">Registered Medical Practitioner (Doctor)</SelectItem>
                  <SelectItem value="asha_worker">ASHA / Community Health Worker</SelectItem>
                  <SelectItem value="admin">Clinic Administrator</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Clinician / User ID</Label>
              <Input
                placeholder="e.g. dr_arun_kumar"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Account Password</Label>
              <Input
                type="password"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="text-[11px] text-muted-foreground">
                Demo credentials default: {role === 'doctor' ? 'grannus_secure_doctor_2026' : 'grannus_secure_admin_2026'}
              </p>
            </div>

            {role === 'doctor' && (
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
                    Required under MCI Telemedicine Guidelines 2020 for lawful digital prescription signing.
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

            {errorMessage && (
              <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-lg flex items-center gap-2 text-xs text-destructive">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {successMessage && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg flex items-center gap-2 text-xs text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{successMessage}</span>
              </div>
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
