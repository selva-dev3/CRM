'use client';

import React from 'react';
import { 
  TrendingUp, 
  Users, 
  DollarSign, 
  Sparkles, 
  ArrowUpRight, 
  Briefcase, 
  CheckCircle2, 
  Clock, 
  Plus,
  Search,
  Filter
} from 'lucide-react';
import { Button, Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui';

export default function DashboardPage() {
  const stats = [
    {
      title: 'Total Active Leads',
      value: '1,248',
      change: '+12.5%',
      isPositive: true,
      icon: Users,
      badge: 'High Intent',
      bgGradient: 'from-blue-500/10 to-indigo-500/10',
      iconColor: 'text-indigo-600',
      iconBg: 'bg-indigo-100',
    },
    {
      title: 'Pipeline Revenue',
      value: '$452,000',
      change: '+18.2%',
      isPositive: true,
      icon: DollarSign,
      badge: 'Q3 Forecast',
      bgGradient: 'from-emerald-500/10 to-teal-500/10',
      iconColor: 'text-emerald-600',
      iconBg: 'bg-emerald-100',
    },
    {
      title: 'Avg Win Rate',
      value: '64.2%',
      change: '+3.4%',
      isPositive: true,
      icon: TrendingUp,
      badge: 'Above Target',
      bgGradient: 'from-amber-500/10 to-orange-500/10',
      iconColor: 'text-amber-600',
      iconBg: 'bg-amber-100',
    },
    {
      title: 'AI Quality Score',
      value: '88/100',
      change: 'Optimal',
      isPositive: true,
      icon: Sparkles,
      badge: 'AI Verified',
      bgGradient: 'from-purple-500/10 to-violet-500/10',
      iconColor: 'text-purple-600',
      iconBg: 'bg-purple-100',
    },
  ];

  const recentDeals = [
    { company: 'Acme Global Corp', dealValue: '$120,000', stage: 'Contract Sent', status: 'high', owner: 'Selva Admin' },
    { company: 'Nexus Tech Solutions', dealValue: '$85,000', stage: 'Negotiation', status: 'medium', owner: 'Alex Rivera' },
    { company: 'Starlight Logistics', dealValue: '$45,000', stage: 'Qualified Lead', status: 'new', owner: 'Sarah Jenkins' },
    { company: 'Hyperion Cloud Inc', dealValue: '$210,000', stage: 'Closing Stage', status: 'high', owner: 'Selva Admin' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Sales & CRM Overview
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time revenue pipeline, lead performance & AI insights
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="hidden sm:inline-flex">
            <Filter className="w-4 h-4 mr-1.5 text-slate-500" />
            Filter Period
          </Button>
          <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm">
            <Plus className="w-4 h-4 mr-1.5" />
            New Deal
          </Button>
        </div>
      </div>

      {/* Top Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        {stats.map((stat, idx) => {
          const Icon = stat.icon;
          return (
            <Card key={idx} className="relative overflow-hidden border border-slate-200/80 bg-white hover:border-indigo-200 transition-all duration-200 shadow-xs">
              <div className="p-5">
                <div className="flex items-center justify-between">
                  <div className={`w-10 h-10 rounded-xl ${stat.iconBg} flex items-center justify-center ${stat.iconColor}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                    {stat.badge}
                  </span>
                </div>
                <div className="mt-4">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    {stat.title}
                  </p>
                  <div className="flex items-baseline justify-between mt-1">
                    <h3 className="text-2xl font-black text-slate-900 tracking-tight">
                      {stat.value}
                    </h3>
                    <span className="inline-flex items-center text-xs font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
                      <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />
                      {stat.change}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Main Content Grid: Pipeline Table & AI Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Recent Deals Table */}
        <Card className="lg:col-span-8 border border-slate-200 bg-white shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <div>
              <CardTitle className="text-lg font-bold text-slate-900">
                Top Priority Opportunities
              </CardTitle>
              <CardDescription>Active deals closing this month</CardDescription>
            </div>
            <Button variant="ghost" size="sm" className="text-indigo-600 text-xs font-semibold">
              View All Deals
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-y border-slate-100 bg-slate-50/70 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <th className="py-3 px-6">Company</th>
                    <th className="py-3 px-6">Value</th>
                    <th className="py-3 px-6">Stage</th>
                    <th className="py-3 px-6">Owner</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentDeals.map((deal, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/80 transition duration-150">
                      <td className="py-4 px-6 font-semibold text-slate-900 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center font-bold text-indigo-600 text-xs">
                          {deal.company.charAt(0)}
                        </div>
                        <span>{deal.company}</span>
                      </td>
                      <td className="py-4 px-6 font-bold text-slate-900 tabular-nums">
                        {deal.dealValue}
                      </td>
                      <td className="py-4 px-6">
                        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100">
                          {deal.stage}
                        </span>
                      </td>
                      <td className="py-4 px-6 text-slate-600 text-xs font-medium">
                        {deal.owner}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* AI Recommendations Panel */}
        <Card className="lg:col-span-4 border border-indigo-100 bg-gradient-to-b from-indigo-50/50 via-white to-white shadow-xs">
          <CardHeader>
            <div className="flex items-center space-x-2">
              <div className="p-2 rounded-lg bg-indigo-600 text-white shadow-xs">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-base font-bold text-slate-900">
                  AI Sales Recommendations
                </CardTitle>
                <CardDescription className="text-slate-500">Automated deal velocity insights</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-3.5 rounded-xl bg-white border border-indigo-100 shadow-2xs">
              <div className="flex items-start space-x-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-bold text-slate-900">Follow up with Hyperion Cloud</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">High intent detected. 89% likelihood to close within 48h.</p>
                </div>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-white border border-amber-100 shadow-2xs">
              <div className="flex items-start space-x-3">
                <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-bold text-slate-900">Contract Stagnant: Nexus Tech</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">No response in 5 days. Send automated follow-up sequence.</p>
                </div>
              </div>
            </div>

            <Button variant="outline" className="w-full text-xs font-semibold border-indigo-200 text-indigo-600 hover:bg-indigo-50">
              Generate AI Executive Briefing
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
