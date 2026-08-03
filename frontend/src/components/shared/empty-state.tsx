import React from 'react';
import { Layers } from 'lucide-react';

interface EmptyStateProps {
  readonly title: string;
  readonly description: string;
  readonly icon?: React.ReactNode;
}

export function EmptyState({ title, description, icon }: EmptyStateProps): React.JSX.Element {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center text-slate-400 mb-3 border border-slate-200">
        {icon ?? <Layers className="w-6 h-6" />}
      </div>
      <h3 className="text-base font-black text-slate-900">{title}</h3>
      <p className="text-xs font-bold text-slate-500 max-w-sm mt-1">{description}</p>
    </div>
  );
}
