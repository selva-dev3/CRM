'use client';

import React from 'react';
import Link from 'next/link';

export default function LoginPage() {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold">Welcome Back</h1>
        <p className="text-sm text-gray-400">Sign in to Enterprise CRM</p>
      </div>
      <form className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-300">Email</label>
          <input
            type="email"
            placeholder="admin@company.com"
            className="w-full mt-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300">Password</label>
          <input
            type="password"
            placeholder="••••••••"
            className="w-full mt-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-indigo-500"
          />
        </div>
        <button
          type="submit"
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 font-semibold rounded-lg transition"
        >
          Sign In
        </button>
      </form>
      <div className="text-center text-sm text-gray-400">
        Don&apos;t have an account?{' '}
        <Link href="/register" className="text-indigo-400 hover:underline">
          Register
        </Link>
      </div>
    </div>
  );
}
