import Link from 'next/link';

export default function RegisterPage() {
  return <div className="space-y-4">
    <h1 className="text-2xl font-semibold">Registration is invitation-only</h1>
    <p>Contact your administrator for an invitation to join your organization.</p>
    <Link href="/login" className="font-medium underline">Return to sign in</Link>
  </div>;
}
