import React from 'react';
import Link from 'next/link';
import { ShieldCheck, Sparkles, TrendingUp, Users, Zap } from 'lucide-react';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-12 bg-slate-50 text-slate-900 font-sans selection:bg-indigo-500 selection:text-white">
      {/* Left product panel */}
      <div className="hidden lg:flex lg:col-span-6 xl:col-span-7 relative flex-col justify-between p-12 bg-gradient-to-br from-indigo-900 via-indigo-950 to-slate-900 text-white overflow-hidden shadow-xl">
        {/* Background Ambient Glowing Orbs */}
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/2 -right-24 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl pointer-events-none" />

        {/* Top Logo Header */}
        <div className="relative z-10">
          <Link href="/" className="inline-flex items-center space-x-3 group">
            <div className="w-10 h-10 rounded-xl bg-white p-0.5 shadow-lg group-hover:scale-105 transition-transform duration-300">
              <div className="w-full h-full bg-indigo-600 rounded-[10px] flex items-center justify-center">
                <Zap className="w-5 h-5 text-white fill-white/20" />
              </div>
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-extrabold tracking-tight text-white">
                Enterprise CRM
              </span>
              <span className="text-[10px] tracking-wider uppercase font-semibold text-indigo-200">
                Revenue intelligence workspace
              </span>
            </div>
          </Link>
        </div>

        {/* Middle Hero Content */}
        <div className="relative z-10 max-w-lg my-auto py-12">
          <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full bg-white/10 border border-white/20 text-indigo-100 text-xs font-medium mb-6 backdrop-blur-md">
            <Sparkles className="w-3.5 h-3.5 text-indigo-300" />
            <span>Built for focused revenue teams</span>
          </div>

          <p className="text-4xl xl:text-5xl font-black tracking-tight text-white leading-tight mb-6">
            Accelerate Deals & Close More Revenue with <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-200 via-white to-purple-200">Precision AI</span>
          </p>

          <p className="text-indigo-100/80 text-base leading-relaxed mb-8">
            Keep customer context, pipeline activity, and team workflows together in one secure workspace.
          </p>

          {/* Feature Highlights Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-2xl bg-white/10 border border-white/15 backdrop-blur-sm">
              <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-indigo-200 mb-3">
                <TrendingUp className="w-4 h-4" />
              </div>
              <h4 className="text-sm font-semibold text-white">AI-assisted insights</h4>
              <p className="text-xs text-indigo-200/80 mt-1">Prioritize opportunities with clearer sales signals</p>
            </div>

            <div className="p-4 rounded-2xl bg-white/10 border border-white/15 backdrop-blur-sm">
              <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-indigo-200 mb-3">
                <Users className="w-4 h-4" />
              </div>
              <h4 className="text-sm font-semibold text-white">Multi-tenant controls</h4>
              <p className="text-xs text-indigo-200/80 mt-1">Organize teams with role-based workspace access</p>
            </div>
          </div>
        </div>

        {/* Bottom security context */}
        <div className="relative z-10 pt-6 border-t border-white/10 flex items-center justify-between text-xs text-indigo-200/80">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Secure account access</span>
          </div>
          <span>Role-based workspace protection</span>
        </div>
      </div>

      {/* Right Form Container */}
      <div className="lg:col-span-6 xl:col-span-5 flex items-center justify-center p-4 py-8 sm:p-12 relative bg-slate-50">
        <div className="w-full max-w-md space-y-5">
          <Link href="/" className="inline-flex items-center gap-2.5 lg:hidden">
            <span className="flex size-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
              <Zap className="size-5" aria-hidden="true" />
            </span>
            <span className="text-lg font-extrabold tracking-tight text-slate-900">Enterprise CRM</span>
          </Link>
          <div className="w-full space-y-8 bg-white p-5 sm:p-8 rounded-2xl border border-slate-200 shadow-xl shadow-slate-200/50">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
