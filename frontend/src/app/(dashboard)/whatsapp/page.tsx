'use client';

import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import { WhatsAppInbox } from '@/components/features/whatsapp/whatsapp-inbox';

export default function WhatsAppPage() {
  return <main className="space-y-5 p-4 sm:p-6"><div><h1 className="text-2xl font-bold">WhatsApp</h1><p className="text-sm text-muted-foreground">Organization-scoped customer conversations and delivery status.</p></div><Suspense fallback={<Loader2 className="size-6 animate-spin" />}><WhatsAppInbox /></Suspense></main>;
}
