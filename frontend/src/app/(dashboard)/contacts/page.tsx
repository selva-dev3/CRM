import React from 'react';

export default function ContactsPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Contact Management</h1>
          <p className="text-gray-400 text-sm">Manage customer relationships and contact details</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm">
          + Add Contact
        </button>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-gray-300">
        <p className="text-sm">Contact directory & interaction history ready.</p>
      </div>
    </div>
  );
}
