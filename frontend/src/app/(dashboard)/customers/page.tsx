'use client';

import { useState } from 'react';
import Link from 'next/link';
import { HeartHandshake } from 'lucide-react';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ModuleError } from '@/components/common/module-page-state';
import { useCustomers, type Customer } from '@/lib/api/crm-extensions';

export default function CustomersPage(){const[page,setPage]=useState(1);const[search,setSearch]=useState('');const query=useCustomers(page,search);const columns:DataTableColumn<Customer>[]=[{id:'name',header:'CUSTOMER',cell:(item)=><Link className="font-semibold text-indigo-700 hover:underline" href={`/${item.entity_type==='contact'?'contacts':'companies'}/${item.entity_id}`}>{item.name}</Link>},{id:'type',header:'TYPE',cell:(item)=><span className="capitalize">{item.entity_type}</span>},{id:'email',header:'EMAIL',cell:(item)=>item.email||'—'},{id:'tickets',header:'OPEN TICKETS',cell:(item)=>item.open_tickets}];return <div className="space-y-6 pb-12"><header><h1 className="flex items-center gap-2 text-2xl font-bold"><HeartHandshake className="text-indigo-600"/>Customers</h1><p className="text-sm text-slate-500">Contacts and companies with completed sales relationships.</p></header>{query.isError&&<ModuleError message="Customers could not be loaded." retry={()=>query.refetch()}/>}<DataTable columns={columns} data={query.data?.items??[]} getRowKey={(item)=>`${item.entity_type}:${item.entity_id}`} emptyTitle="No customers" emptyDescription="Customers appear after a deal is won." searchValue={search} onSearchChange={(value)=>{setSearch(value);setPage(1)}} isLoading={query.isLoading} pagination={{pageIndex:page-1,pageCount:Math.max(1,Math.ceil((query.data?.total??0)/20)),totalRecords:query.data?.total,onPageChange:(next)=>setPage(next+1)}}/></div>}
