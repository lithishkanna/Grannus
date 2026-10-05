'use client';
import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Home,
  Mic,
  LayoutDashboard,
  Menu,
  ShieldCheck,
  History,
  User,
  Stethoscope,
  LogOut,
  Users,
} from 'lucide-react';
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { logoutUser } from '@/lib/api';

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();

  const [currentUser, setCurrentUser] = useState<any | null>(null);
  const [activeProfile, setActiveProfile] = useState<any | null>(null);
  const [isClient, setIsClient] = useState(false);

  const syncAuth = useCallback(() => {
    if (typeof window === 'undefined') return;
    try {
      const userRaw = localStorage.getItem('grannus_user');
      const profileRaw = localStorage.getItem('grannus_active_profile');
      setCurrentUser(userRaw ? JSON.parse(userRaw) : null);
      setActiveProfile(profileRaw ? JSON.parse(profileRaw) : null);
    } catch {
      setCurrentUser(null);
      setActiveProfile(null);
    }
  }, []);

  useEffect(() => {
    setIsClient(true);
    syncAuth();

    const handleAuthChange = () => syncAuth();
    window.addEventListener('storage', handleAuthChange);
    window.addEventListener('grannus_auth_change', handleAuthChange);

    return () => {
      window.removeEventListener('storage', handleAuthChange);
      window.removeEventListener('grannus_auth_change', handleAuthChange);
    };
  }, [syncAuth]);

  // Sync when route changes (e.g. after login/profile select)
  useEffect(() => {
    syncAuth();
  }, [pathname, syncAuth]);

  const handleLogout = async () => {
    await logoutUser();
    setCurrentUser(null);
    setActiveProfile(null);
    router.push('/login');
  };

  const links = [
    { href: '/', label: 'Home', icon: Home },
    { href: '/input', label: 'Voice Input', icon: Mic },
    { href: '/history', label: 'History', icon: History },
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  ];

  const isPatient = currentUser?.role === 'patient';
  const isClinician = currentUser && ['doctor', 'nurse', 'admin'].includes(currentUser.role);

  return (
    <nav className="sticky top-0 z-50 w-full bg-background/80 backdrop-blur-md border-b border-border shadow-sm">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between gap-4">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="font-heading text-2xl font-semibold text-primary tracking-tight">Grannus</span>
          <span className="text-muted-foreground text-sm hidden sm:inline-block">— RuralCare AI</span>
        </Link>

        {/* Desktop Nav Links */}
        <div className="hidden lg:flex items-center gap-6">
          {links.map((link) => {
            const isActive = pathname === link.href;
            const Icon = link.icon;
            return (
              <Link key={link.href} href={link.href} className="relative py-2 px-1 group">
                <div
                  className={`flex items-center gap-2 text-sm font-medium transition-colors ${
                    isActive ? 'text-foreground' : 'text-muted-foreground group-hover:text-foreground'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {link.label}
                </div>
                {isActive && (
                  <motion.div
                    layoutId="navbar-indicator"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full"
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  />
                )}
              </Link>
            );
          })}
        </div>

        {/* User Identity on Top Header */}
        <div className="hidden md:flex items-center gap-3">
          {isClient && isPatient && (
            <div className="flex items-center gap-2 pl-2 pr-3 py-1 rounded-full bg-primary/10 border border-primary/20">
              <div className="w-7 h-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-xs shrink-0 shadow-sm">
                {activeProfile?.full_name ? activeProfile.full_name[0].toUpperCase() : 'P'}
              </div>
              <div className="flex flex-col text-left mr-1">
                <span className="font-semibold text-foreground text-xs leading-tight">
                  {activeProfile?.full_name || 'Patient'}
                </span>
                <span className="text-[10px] text-muted-foreground leading-tight">
                  {activeProfile?.relation ? `Patient (${activeProfile.relation})` : 'Patient Account'}
                </span>
              </div>
              <Link
                href="/login"
                className="p-1 rounded-full hover:bg-primary/20 text-muted-foreground hover:text-foreground transition-colors"
                title="Switch family member profile"
              >
                <Users className="w-3.5 h-3.5" />
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="p-1 rounded-full hover:bg-destructive/20 text-muted-foreground hover:text-destructive transition-colors ml-0.5"
                title="Sign out of patient session"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {isClient && isClinician && (
            <div className="flex items-center gap-2 pl-2.5 pr-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30">
              <div className="w-7 h-7 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-sm">
                <Stethoscope className="w-3.5 h-3.5" />
              </div>
              <div className="flex flex-col text-left mr-1">
                <span className="font-semibold text-foreground text-xs leading-tight">
                  {currentUser.full_name || 'Medical Officer'}
                </span>
                <span className="text-[10px] text-emerald-700 dark:text-emerald-400 font-mono leading-tight">
                  {currentUser.doctor_registration_number || currentUser.role.toUpperCase()}
                </span>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="p-1 rounded-full hover:bg-destructive/20 text-muted-foreground hover:text-destructive transition-colors ml-1"
                title="Sign out of clinician workstation"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {isClient && !currentUser && (
            <Link href="/login">
              <Button size="sm" variant="outline" className="gap-2 rounded-full text-xs font-medium border-border">
                <ShieldCheck className="w-4 h-4 text-primary" />
                <span>Clinician Login</span>
              </Button>
            </Link>
          )}
        </div>

        {/* Mobile Hamburger Drawer */}
        <div className="md:hidden flex items-center gap-2">
          {isClient && isPatient && (
            <div className="w-7 h-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-xs shrink-0">
              {activeProfile?.full_name ? activeProfile.full_name[0].toUpperCase() : 'P'}
            </div>
          )}
          {isClient && isClinician && (
            <div className="w-7 h-7 rounded-full bg-emerald-600 text-white flex items-center justify-center text-xs shrink-0">
              <Stethoscope className="w-3.5 h-3.5" />
            </div>
          )}

          <Sheet>
            <SheetTrigger className="p-2 rounded-lg hover:bg-muted text-foreground">
              <Menu className="w-6 h-6" />
            </SheetTrigger>
            <SheetContent side="right" className="w-[280px] sm:w-[320px]">
              <SheetTitle className="font-heading text-xl text-primary mb-4">Grannus</SheetTitle>

              {/* Mobile Active User Card */}
              {isClient && currentUser && (
                <div className="p-3 mb-4 rounded-xl bg-muted/60 border border-border flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${
                      isClinician ? 'bg-emerald-600 text-white' : 'bg-primary text-primary-foreground'
                    }`}>
                      {isClinician ? <Stethoscope className="w-4 h-4" /> : (activeProfile?.full_name ? activeProfile.full_name[0].toUpperCase() : 'P')}
                    </div>
                    <div className="flex flex-col text-left">
                      <span className="font-semibold text-foreground text-xs leading-tight">
                        {isClinician ? (currentUser.full_name || 'Medical Officer') : (activeProfile?.full_name || 'Patient')}
                      </span>
                      <span className="text-[10px] text-muted-foreground leading-tight mt-0.5">
                        {isClinician ? (currentUser.doctor_registration_number || currentUser.role) : `Profile: ${activeProfile?.relation || 'Self'}`}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                    title="Sign Out"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              )}

              <div className="flex flex-col gap-2">
                {links.map((link) => {
                  const isActive = pathname === link.href;
                  const Icon = link.icon;
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                        isActive ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:bg-muted'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <span>{link.label}</span>
                    </Link>
                  );
                })}

                <div className="pt-4 mt-2 border-t border-border flex flex-col gap-2">
                  {currentUser ? (
                    <>
                      {isPatient && (
                        <Link
                          href="/login"
                          className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-xs text-muted-foreground hover:bg-muted"
                        >
                          <Users className="w-4 h-4" />
                          <span>Switch Family Profile</span>
                        </Link>
                      )}
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-xs text-destructive hover:bg-destructive/10 text-left font-medium"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Sign Out Session</span>
                      </button>
                    </>
                  ) : (
                    <Link
                      href="/login"
                      className="flex items-center gap-3 px-4 py-3 rounded-lg bg-primary text-primary-foreground font-medium text-sm text-center justify-center shadow-sm"
                    >
                      <ShieldCheck className="w-4 h-4" />
                      <span>Sign In / Clinician Portal</span>
                    </Link>
                  )}
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </nav>
  );
}
