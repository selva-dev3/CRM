import React from 'react';
import Link from 'next/link';
import { ShieldCheck, Sparkles, TrendingUp, Users, Zap } from 'lucide-react';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-12 bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white">
      {/* Left Decorative Feature Panel (Visible on lg screens) */}
      <div className="hidden lg:flex lg:col-span-6 xl:col-span-7 relative flex-col justify-between p-12 bg-slate-900/60 border-r border-slate-800/80 overflow-hidden">
        {/* Background Ambient Glowing Orbs */}
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/2 -right-24 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 left-1/3 w-96 h-96 bg-emerald-600/15 rounded-full blur-3xl pointer-events-none" />

        {/* Top Logo Header */}
        <div className="relative z-10">
          <Link href="/" className="inline-flex items-center space-x-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-emerald-400 p-0.5 shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform duration-300">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Zap className="w-5 h-5 text-indigo-400 fill-indigo-400/20" />
              </div>
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-100 to-slate-400">
                Enterprise CRM
              </span>
              <span className="text-[10px] tracking-wider uppercase font-semibold text-indigo-400">
                AI-Powered Growth Engine
              </span>
            </div>
          </Link>
        </div>

        {/* Middle Hero Content */}
        <div className="relative z-10 max-w-lg my-auto py-12">
          <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-medium mb-6 backdrop-blur-md">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Next-Gen Sales Intelligence Platform</span>
          </div>

          <h1 className="text-4xl xl:text-5xl font-black tracking-tight text-white leading-tight mb-6">
            Accelerate Deals & Close More Revenue with <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-400 to-emerald-400">Precision AI</span>
          </h1>

          <p className="text-slate-400 text-base leading-relaxed mb-8">
            Empower your revenue teams with automated lead scoring, real-time pipeline analytics, seamless email outreach, and enterprise-grade security.
          </p>

          {/* Feature Highlights Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-sm">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400 mb-3">
                <TrendingUp className="w-4 h-4" />
              </div>
              <h4 className="text-sm font-semibold text-white">99.4% Win Rate AI</h4>
              <p className="text-xs text-slate-400 mt-1">Predictive lead scoring & conversion insights</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-sm">
              <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-400 mb-3">
                <Users className="w-4 h-4" />
              </div>
              <h4 className="text-sm font-semibold text-white">Multi-Tenant CRM</h4>
              <p className="text-xs text-slate-400 mt-1">Role-based access & organization routing</p>
            </div>
          </div>
        </div>

        {/* Bottom Footer Trust Badge */}
        <div className="relative z-10 pt-6 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>256-Bit SSL Encrypted & SOC2 Compliant</span>
          </div>
          <span>API Connected: <code className="text-indigo-300 font-mono">crm-dev3.up.railway.app</code></span>
        </div>
      </div>

      {/* Right Form Container */}
      <div className="lg:col-span-6 xl:col-span-5 flex items-center justify-center p-6 sm:p-12 relative">
        <div className="w-full max-w-md space-y-8">
          {children}
        </div>
      </div>
    </div>
  );
}
