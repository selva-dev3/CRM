import Link from 'next/link';
import { ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function InactivePage() {
  return (
    <div className="space-y-5 text-center">
      <ShieldAlert className="mx-auto size-12 text-amber-600" aria-hidden="true" />
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Account inactive</h1>
        <p className="mt-2 text-sm text-slate-600">
          Contact your organization administrator to restore access.
        </p>
      </div>
      <Button asChild variant="outline"><Link href="/login">Return to sign in</Link></Button>
    </div>
  );
}
