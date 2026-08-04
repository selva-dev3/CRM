'use client';

import React, { useState, useEffect } from 'react';
import { Building2, Globe, Users, Briefcase } from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { useCompaniesQuery, CompanyItem } from '@/lib/api/companies';

export default function CompaniesPage() {
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

  const { data: companies = [], isLoading } = useCompaniesQuery(page, limit, debouncedSearchTerm);

  const columns: DataTableColumn<CompanyItem>[] = [
    {
      id: 'name',
      header: 'Company Name',
      cell: (item) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-700 font-bold text-xs">
            <Building2 className="w-4 h-4" />
          </div>
          <div>
            <div className="font-semibold text-slate-900">{item.name}</div>
            <div className="text-xs text-slate-500">{item.website || 'N/A'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'industry',
      header: 'Industry Sector',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Briefcase className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.industry || 'General Business'}</span>
        </div>
      ),
    },
    {
      id: 'website',
      header: 'Website Domain',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-blue-600 text-xs font-medium">
          <Globe className="w-3.5 h-3.5 text-blue-400" />
          <a href={`https://${item.website}`} target="_blank" rel="noreferrer" className="hover:underline">
            {item.website || 'N/A'}
          </a>
        </div>
      ),
    },
    {
      id: 'employee_count',
      header: 'Company Size',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Users className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.employee_count ? `${item.employee_count} employees` : 'Enterprise'}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Company Management</h1>
          <p className="text-slate-500 text-sm">Track accounts, company profiles, and organization hierarchy</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm">
          + Add Company
        </button>
      </div>

      <DataTable<CompanyItem>
        columns={columns}
        data={companies}
        getRowKey={(item) => item.id}
        emptyTitle="No companies found"
        emptyDescription="Add companies or try searching with a different term."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search company name or domain..."
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: companies.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + companies.length,
        }}
      />
    </div>
  );
}
