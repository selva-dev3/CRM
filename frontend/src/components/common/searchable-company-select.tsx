'use client';

import { useState } from 'react';
import { Check, ChevronDown, Search } from 'lucide-react';
import type { CompanyItem } from '@/lib/api/companies';

export interface SearchableCompanySelectProps {
  value: string;
  onChange: (val: string) => void;
  companies: Pick<CompanyItem, 'id' | 'name'>[];
}

export function SearchableCompanySelect({
  value,
  onChange,
  companies,
}: SearchableCompanySelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');

  const selectedCompany = companies.find((c) => c.id === value);
  const filteredCompanies = companies.filter((c) =>
    (c.name || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-left text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-between cursor-pointer"
      >
        <span className={selectedCompany ? 'text-slate-900 font-semibold' : 'text-slate-400'}>
          {selectedCompany ? selectedCompany.name : '-- Select Company --'}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-xl p-2 space-y-1.5 animate-in fade-in-50">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search company by name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-8 pl-8 pr-2 text-xs rounded-md border border-slate-200 bg-slate-50 text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
            />
          </div>

          <div className="max-h-40 overflow-y-auto space-y-0.5">
            <button
              type="button"
              onClick={() => {
                onChange('');
                setIsOpen(false);
                setSearch('');
              }}
              className="w-full px-2 py-1.5 text-left text-xs text-slate-500 hover:bg-slate-100 rounded cursor-pointer"
            >
              -- None / Clear Selection --
            </button>
            {filteredCompanies.length === 0 ? (
              <div className="px-2 py-2 text-xs text-slate-400 text-center">No matching companies</div>
            ) : (
              filteredCompanies.map((comp) => (
                <button
                  key={comp.id}
                  type="button"
                  onClick={() => {
                    onChange(comp.id);
                    setIsOpen(false);
                    setSearch('');
                  }}
                  className={`w-full px-2 py-1.5 text-left text-xs rounded transition flex items-center justify-between cursor-pointer ${
                    value === comp.id ? 'bg-blue-50 text-blue-700 font-bold' : 'text-slate-800 hover:bg-slate-100'
                  }`}
                >
                  <span>{comp.name}</span>
                  {value === comp.id && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
