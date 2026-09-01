'use client';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Mic, Activity, Shield, Brain } from 'lucide-react';
import { SUPPORTED_LANGUAGES } from '@/lib/api';

export default function LandingPage() {
  const router = useRouter();

  const features = [
    {
      title: 'Voice-First Input',
      desc: 'Patients speak naturally in their native language without complex forms.',
      icon: Mic
    },
    {
      title: 'AI Triage',
      desc: 'Intelligently extracts symptoms and assigns priority using medical LLMs.',
      icon: Brain
    },
    {
      title: 'Safety First',
      desc: 'Automatically flags critical symptoms and warns patients immediately.',
      icon: Shield
    }
  ];

  return (
    <div className="w-full">
      {/* Hero Section */}
      <section className="relative py-20 lg:py-32 overflow-hidden px-4">
        <div className="container mx-auto max-w-5xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="mb-6"
          >
            <h1 className="text-5xl md:text-7xl font-heading font-medium tracking-tight text-primary mb-2">
              Grannus
            </h1>
            <h2 className="text-2xl md:text-3xl text-foreground font-light mb-6">RuralCare AI</h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
              Bridging the healthcare & language gap between rural patients and urban doctors through intelligent voice triage.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4, duration: 0.8 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4 mt-10"
          >
            <Button 
              size="lg" 
              onClick={() => router.push('/input')}
              className="w-full sm:w-auto text-lg h-14 px-8 rounded-full shadow-lg bg-primary hover:bg-primary/90 text-primary-foreground gap-2"
            >
              <Mic className="w-5 h-5" /> Start Consultation
            </Button>
            <Button 
              size="lg" 
              variant="outline"
              onClick={() => router.push('/dashboard')}
              className="w-full sm:w-auto text-lg h-14 px-8 rounded-full bg-card gap-2"
            >
              <Activity className="w-5 h-5" /> View Dashboard
            </Button>
          </motion.div>
        </div>
        
        {/* Abstract background blobs */}
        <div className="absolute top-1/2 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-primary/5 rounded-full blur-3xl -z-10" />
        <div className="absolute top-1/2 right-1/4 translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-accent/30 rounded-full blur-3xl -z-10" />
      </section>

      {/* Features */}
      <section className="py-20 bg-muted/30 border-y border-border px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {features.map((f, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.2 }}
                className="bg-card p-8 rounded-2xl border border-border shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="w-12 h-12 bg-primary/10 text-primary rounded-xl flex items-center justify-center mb-6">
                  <f.icon className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-heading font-medium text-foreground mb-3">{f.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Languages */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-4xl text-center">
          <h2 className="text-3xl font-heading font-medium text-foreground mb-12">Multilingual Support</h2>
          <div className="flex flex-wrap justify-center gap-3">
            {SUPPORTED_LANGUAGES.filter(l => l.code !== 'unknown' && l.code !== 'en-IN').map((lang, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="px-6 py-3 bg-card border border-border rounded-full text-foreground shadow-sm hover:shadow-md transition-shadow cursor-default flex items-center gap-2"
              >
                <span className="font-medium">{lang.name}</span>
                <span className="text-muted-foreground/60 text-sm">|</span>
                <span className="text-muted-foreground text-sm">{lang.nativeName}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
