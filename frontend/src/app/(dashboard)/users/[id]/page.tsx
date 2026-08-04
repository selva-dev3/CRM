'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Mail,
  ShieldCheck,
  UserCheck,
  Building,
  Calendar,
  Pencil,
  Trash2,
  Ban,
  CheckCircle2,
  AlertCircle,
  Activity,
  Key,
  Award,
  RefreshCw,
  User,
  Power
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  useUserQuery,
  useActivateUserMutation,
  useDeactivateUserMutation,
  useDeleteUserMutation,
} from '@/lib/api/users';
import { useOrganizationsQuery } from '@/lib/api/organizations';

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = params?.id as string;

  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'activity'>('profile');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: user, isLoading, isError, refetch } = useUserQuery(userId);
  const { data: organizations = [] } = useOrganizationsQuery();

  const activateUserMutation = useActivateUserMutation();
  const deactivateUserMutation = useDeactivateUserMutation();
  const deleteUserMutation = useDeleteUserMutation();

  const orgName = organizations.find((o) => o.id === user?.organization_id)?.name || user?.organization_id || 'Primary Org';

  const handleToggleStatus = async () => {
    if (!user) return;
    try {
      if (user.is_active) {
        await deactivateUserMutation.mutateAsync(user.id);
        setSuccessMessage(`User '${user.name}' has been deactivated successfully.`);
      } else {
        await activateUserMutation.mutateAsync(user.id);
        setSuccessMessage(`User '${user.name}' has been activated successfully.`);
      }
      refetch();
    } catch {
      setErrorMessage('Failed to update user status.');
    }
  };

  const handleDelete = async () => {
    if (!user) return;
    if (confirm(`Are you sure you want to delete user ${user.name}?`)) {
      try {
        await deleteUserMutation.mutateAsync(user.id);
        router.push('/users');
      } catch {
        setErrorMessage('Failed to delete user.');
      }
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
        <p className="text-sm font-medium text-slate-500">Loading user profile details...</p>
      </div>
    );
  }

  if (isError || !user) {
    return (
      <div className="space-y-6">
        <Link
          href="/users"
          className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-900 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Users</span>
        </Link>

        <div className="p-8 text-center bg-white rounded-xl border border-slate-200 shadow-sm max-w-lg mx-auto">
          <AlertCircle className="w-12 h-12 text-rose-500 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-slate-900">User Not Found</h2>
          <p className="text-sm text-slate-500 mt-1 mb-4">
            The requested user profile (ID: {userId}) could not be located or has been removed.
          </p>
          <Button onClick={() => router.push('/users')}>Return to User Directory</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <Link
            href="/users"
            className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-blue-600 mb-2 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Team Directory</span>
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
            <span>{user.name}</span>
            <Badge
              variant="outline"
              className={
                user.is_active
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                  : 'bg-amber-50 text-amber-700 border-amber-300'
              }
            >
              {user.is_active ? 'Active Account' : 'Deactivated'}
            </Badge>
          </h1>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={handleToggleStatus}
            className="border-slate-300 text-slate-700 hover:bg-slate-50 font-semibold text-xs"
          >
            {user.is_active ? (
              <>
                <Ban className="w-3.5 h-3.5 mr-1.5 text-amber-600" />
                Deactivate
              </>
            ) : (
              <>
                <Power className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
                Activate Account
              </>
            )}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleDelete}
            className="border-rose-300 text-rose-600 hover:bg-rose-50 font-semibold text-xs"
          >
            <Trash2 className="w-3.5 h-3.5 mr-1.5" />
            Delete User
          </Button>
        </div>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-sm font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-sm font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Header Profile Overview Card */}
      <Card className="p-6 border border-slate-200 bg-white shadow-sm rounded-xl">
        <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-blue-600 text-white font-extrabold text-2xl shadow-md shrink-0">
            {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
          </div>

          <div className="space-y-1.5 flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xl font-bold text-slate-900 truncate">{user.name}</h2>
              <span className="px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 font-semibold text-xs border border-blue-200">
                {user.role}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs font-medium text-slate-600 pt-1">
              <div className="flex items-center gap-1.5">
                <Mail className="w-4 h-4 text-slate-400" />
                <span>{user.email}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Building className="w-4 h-4 text-slate-400" />
                <span>{orgName}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-slate-400" />
                <span>Joined {user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</span>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Tab Navigation */}
      <div className="flex items-center border-b border-slate-200 gap-6 text-sm font-semibold text-slate-600">
        <button
          onClick={() => setActiveTab('profile')}
          className={`pb-3 cursor-pointer transition border-b-2 ${
            activeTab === 'profile' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          Profile Details
        </button>
        <button
          onClick={() => setActiveTab('security')}
          className={`pb-3 cursor-pointer transition border-b-2 ${
            activeTab === 'security' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          Security & Permissions
        </button>
        <button
          onClick={() => setActiveTab('activity')}
          className={`pb-3 cursor-pointer transition border-b-2 ${
            activeTab === 'activity' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          Activity Audit Logs
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'profile' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2 border-b border-slate-100 pb-3">
              <User className="w-4 h-4 text-blue-600" />
              <span>User Information</span>
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-500 font-medium block">Full Name</span>
                <span className="font-semibold text-slate-900 text-sm">{user.name}</span>
              </div>
              <div>
                <span className="text-slate-500 font-medium block">Email Address</span>
                <span className="font-semibold text-slate-900 text-sm">{user.email}</span>
              </div>
              <div>
                <span className="text-slate-500 font-medium block">User ID</span>
                <span className="font-mono text-slate-700 bg-slate-100 px-2 py-0.5 rounded text-[11px]">{user.id}</span>
              </div>
            </div>
          </Card>

          <Card className="p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2 border-b border-slate-100 pb-3">
              <ShieldCheck className="w-4 h-4 text-blue-600" />
              <span>Organization & Role Scope</span>
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-500 font-medium block">Assigned Role</span>
                <span className="font-semibold text-slate-900 text-sm">{user.role}</span>
              </div>
              <div>
                <span className="text-slate-500 font-medium block">Organization Unit</span>
                <span className="font-semibold text-slate-900 text-sm">{orgName}</span>
              </div>
              <div>
                <span className="text-slate-500 font-medium block">Account Status</span>
                <span className={`font-bold ${user.is_active ? 'text-emerald-600' : 'text-amber-600'}`}>
                  {user.is_active ? 'Active & Operational' : 'Inactive'}
                </span>
              </div>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'security' && (
        <Card className="p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2 border-b border-slate-100 pb-3">
            <Key className="w-4 h-4 text-blue-600" />
            <span>Security & Access Rights</span>
          </h3>
          <div className="space-y-3 text-xs text-slate-700">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-900">Multi-Factor Authentication (MFA)</div>
                <div className="text-slate-500">Enhanced account security protocol</div>
              </div>
              <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-300">
                Enabled
              </Badge>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-900">Effective Permissions</div>
                <div className="text-slate-500">Leads, Contacts, Companies, Deals Management</div>
              </div>
              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-300">
                {user.role} Access
              </Badge>
            </div>
          </div>
        </Card>
      )}

      {activeTab === 'activity' && (
        <Card className="p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2 border-b border-slate-100 pb-3">
            <Activity className="w-4 h-4 text-blue-600" />
            <span>User System Audit Log</span>
          </h3>
          <div className="space-y-3 text-xs">
            <div className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
              <div>
                <div className="font-bold text-slate-900">User Login Authenticated</div>
                <div className="text-slate-500">IP: 192.168.1.45 · Session active</div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <Pencil className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
              <div>
                <div className="font-bold text-slate-900">Profile Details Synchronized</div>
                <div className="text-slate-500">Updated organization role preferences</div>
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
