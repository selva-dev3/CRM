import type { ReactNode } from 'react';

import type { AIActionProposal } from '@/lib/api/ai';

const previewFields = [
  ['title', 'Task title'],
  ['status', 'Initial status'],
  ['description', 'Description'],
  ['due_date', 'Due date'],
  ['priority', 'Priority'],
  ['assigned_to', 'Assignee'],
  ['lead_id', 'Lead'],
  ['contact_id', 'Contact'],
  ['company_id', 'Company'],
  ['deal_id', 'Deal'],
  ['project_id', 'Project'],
  ['ticket_id', 'Ticket'],
] as const;

export function ActionPreview({
  action,
  controls,
  dark = false,
}: {
  readonly action: AIActionProposal;
  readonly controls: ReactNode;
  readonly dark?: boolean;
}) {
  const visible = previewFields.filter(([key]) => {
    const value = action.payload[key];
    return value !== null && value !== undefined && value !== '';
  });
  return (
    <section
      aria-label={`Confirm ${action.title}`}
      className={dark
        ? 'mt-2 rounded-lg border border-amber-700/60 bg-amber-950/30 p-3'
        : 'rounded-xl border border-amber-200 bg-amber-50 p-3'}
    >
      <h4 className={dark ? 'text-sm font-semibold text-amber-100' : 'text-sm font-semibold text-amber-950'}>
        {action.title}
      </h4>
      <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
        {visible.map(([key, label]) => (
          <div key={key} className="min-w-0">
            <dt className={dark ? 'text-amber-300/70' : 'text-amber-700'}>{label}</dt>
            <dd className={dark ? 'break-words text-amber-50' : 'break-words text-amber-950'}>
              {String(action.payload[key])}
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-3 flex justify-end">{controls}</div>
    </section>
  );
}
