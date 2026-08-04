'use client';

import React, { useState, useEffect } from 'react';
import { CheckSquare, Calendar, AlertCircle, UserCheck } from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { useTasksQuery, TaskItem } from '@/lib/api/tasks';

export default function TasksPage() {
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

  const { data: tasks = [], isLoading } = useTasksQuery(page, limit, debouncedSearchTerm);

  const columns: DataTableColumn<TaskItem>[] = [
    {
      id: 'title',
      header: 'Task Title',
      cell: (item) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700 font-bold text-xs">
            <CheckSquare className="w-4 h-4" />
          </div>
          <div>
            <div className="font-semibold text-slate-900">{item.title}</div>
            <div className="text-xs text-slate-500">{item.status || 'Pending'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'due_date',
      header: 'Due Date',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.due_date || 'No due date'}</span>
        </div>
      ),
    },
    {
      id: 'priority',
      header: 'Priority Level',
      cell: (item) => {
        const p = item.priority || 'Low';
        const badgeColor =
          p === 'High' ? 'bg-rose-100 text-rose-700' : p === 'Medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-700';
        return (
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${badgeColor}`}>
            {p}
          </span>
        );
      },
    },
    {
      id: 'assigned_to',
      header: 'Assigned Representative',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <UserCheck className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.assigned_to || 'Unassigned'}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Task Management</h1>
          <p className="text-slate-500 text-sm">Assign, prioritize, and track sales team tasks</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm">
          + Create Task
        </button>
      </div>

      <DataTable<TaskItem>
        columns={columns}
        data={tasks}
        getRowKey={(item) => item.id}
        emptyTitle="No tasks found"
        emptyDescription="Create a task or change search parameters."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search task title..."
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: tasks.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + tasks.length,
        }}
      />
    </div>
  );
}
