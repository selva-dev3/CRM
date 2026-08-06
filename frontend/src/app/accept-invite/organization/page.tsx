'use client';

import React, { Suspense } from 'react';
import AcceptInvitationPage from './[token]/page';

export default function Page() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-slate-600 font-medium">Loading invitation...</div>}>
      <AcceptInvitationPage />
    </Suspense>
  );
}
