'use client';

import React, { useState, useEffect } from 'react';
import { Mail, Phone, Building, User } from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { useContactsQuery, ContactItem } from '@/lib/api/contacts';

export default function ContactsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 15;

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  const { data: contacts = [], isLoading } = useContactsQuery(page, limit, debouncedSearchTerm);

  const columns: DataTableColumn<ContactItem>[] = [
    {
      id: 'name',
      header: 'Contact Name',
      cell: (item) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs">
            {item.name.charAt(0)}
          </div>
          <div>
            <div className="font-semibold text-slate-900">{item.name}</div>
            <div className="text-xs text-slate-500">{item.position || 'Representative'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'email',
      header: 'Email Address',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Mail className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.email}</span>
        </div>
      ),
    },
    {
      id: 'phone',
      header: 'Phone Number',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Phone className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.phone || 'N/A'}</span>
        </div>
      ),
    },
    {
      id: 'company',
      header: 'Company Account',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Building className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.company_id ? `Org ${item.company_id}` : 'General Account'}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Contact Management</h1>
          <p className="text-slate-500 text-sm">Manage customer relationships and contact details</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm">
          + Add Contact
        </button>
      </div>

      <DataTable<ContactItem>
        columns={columns}
        data={contacts}
        getRowKey={(item) => item.id}
        emptyTitle="No contacts found"
        emptyDescription="Add contacts or try modifying your search filter."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search contact name or email..."
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: contacts.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + contacts.length,
        }}
      />
    </div>
  );
}
