import React from 'react';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
      <div className="w-full max-w-md p-8 bg-gray-900 border border-gray-800 rounded-2xl shadow-xl">
        {children}
      </div>
    </div>
  );
}
