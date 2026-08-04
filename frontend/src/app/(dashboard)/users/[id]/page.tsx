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
  Trash2,
  Ban,
  CheckCircle2,
  AlertCircle,
  Activity,
  Key,
  Award,
  RefreshCw,
  User,
  Power,
  TrendingUp,
  Target,
  DollarSign,
  PhoneCall,
  Users,
  Lock,
  RotateCcw,
  Plus,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  useUserQuery,
  useUserQuotaQuery,
  useUserPerformanceQuery,
  useUserPermissionsQuery,
  useUserActivitiesQuery,
  useUserTeamsQuery,
  useActivateUserMutation,
  useDeactivateUserMutation,
  useDeleteUserMutation,
  useResetUserPasswordAdminMutation,
  useAssignUserTeamMutation,
  useRemoveUserTeamMutation,
  UserTeamItem
} from '@/lib/api/users';
import { useOrganizationsQuery } from '@/lib/api/organizations';

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = params?.id as string;

  const [activeTab, setActiveTab] = useState<'profile' | 'performance' | 'security' | 'activity'>('profile');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Team Create Modal State
  const [isTeamModalOpen, setIsTeamModalOpen] = useState(false);
  const [newTeamName, setNewTeamName] = useState('');
  const [newTeamRole, setNewTeamRole] = useState('Member');

  // Queries
  const { data: user, isLoading, isError, refetch } = useUserQuery(userId);
  const { data: quota } = useUserQuotaQuery(userId);
  const { data: performance } = useUserPerformanceQuery(userId);
  const { data: permissionsData } = useUserPermissionsQuery(userId);
  const { data: activities = [] } = useUserActivitiesQuery(userId);
  const { data: teamsData = [], refetch: refetchTeams } = useUserTeamsQuery(userId);
  const { data: organizations = [] } = useOrganizationsQuery();

  // Local teams state for instant interactive create/delete feedback
  const [localTeams, setLocalTeams] = useState<UserTeamItem[] | null>(null);
  const teams = localTeams ?? teamsData;

  // Mutations
  const activateUserMutation = useActivateUserMutation();
  const deactivateUserMutation = useDeactivateUserMutation();
  const deleteUserMutation = useDeleteUserMutation();
  const resetPasswordMutation = useResetUserPasswordAdminMutation();
  const assignTeamMutation = useAssignUserTeamMutation();
  const removeTeamMutation = useRemoveUserTeamMutation();

  const orgName = organizations.find((o) => o.id === user?.organization_id)?.name || user?.organization_id || 'Primary Org';

  const handleToggleStatus = async () => {
    if (!user) return;
    try {
      setErrorMessage(null);
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

  const handleResetPassword = async () => {
    if (!user) return;
    try {
      setErrorMessage(null);
      const res = await resetPasswordMutation.mutateAsync(user.id);
      setSuccessMessage(res.message || `Temporary password sent to ${user.email}`);
    } catch {
      setErrorMessage('Failed to reset password.');
    }
  };

  const handleCreateTeamSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeamName.trim()) {
      setErrorMessage('Please enter a team name.');
      return;
    }
    try {
      setErrorMessage(null);
      const newTeamId = `team-${Date.now().toString().slice(-4)}`;
      const res = await assignTeamMutation.mutateAsync({
        userId,
        teamId: newTeamId,
        teamName: newTeamName.trim(),
        role: newTeamRole,
      });

      // Update local team list instantly
      const updatedList = [
        ...teams,
        { id: newTeamId, name: newTeamName.trim(), role: newTeamRole }
      ];
      setLocalTeams(updatedList);

      setSuccessMessage(res.message || `Assigned to team '${newTeamName.trim()}' successfully.`);
      setNewTeamName('');
      setNewTeamRole('Member');
      setIsTeamModalOpen(false);
      refetchTeams();
    } catch {
      setErrorMessage('Failed to assign user to team.');
    }
  };

  const handleRemoveTeam = async (teamId: string, teamName: string) => {
    if (confirm(`Are you sure you want to remove ${user?.name} from team '${teamName}'?`)) {
      try {
        setErrorMessage(null);
        const res = await removeTeamMutation.mutateAsync({ userId, teamId });

        // Remove from local teams state
        const updatedList = teams.filter((t) => t.id !== teamId);
        setLocalTeams(updatedList);

        setSuccessMessage(res.message || `Removed from team '${teamName}' successfully.`);
        refetchTeams();
      } catch {
        setErrorMessage('Failed to remove team.');
      }
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
        <p className="text-sm font-medium text-slate-500">Loading user profile and metrics...</p>
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

  const quotaPercent = quota?.target_amount ? Math.min(100, Math.round((quota.achieved_amount / quota.target_amount) * 100)) : 70;

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
            onClick={handleResetPassword}
            disabled={resetPasswordMutation.isPending}
            className="border-slate-300 text-slate-700 hover:bg-slate-50 font-semibold text-xs"
          >
            <RotateCcw className={`w-3.5 h-3.5 mr-1.5 text-blue-600 ${resetPasswordMutation.isPending ? 'animate-spin' : ''}`} />
            Reset Password
          </Button>

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

      {/* Feedback Banners */}
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

      {/* Overview Card */}
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

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 border border-slate-200 bg-white shadow-sm rounded-xl flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-slate-500">Sales Quota Target</div>
            <div className="text-lg font-bold text-slate-900 mt-0.5">
              ${(quota?.target_amount || 125000).toLocaleString()}
            </div>
            <div className="text-[11px] text-emerald-600 font-semibold mt-1">
              ${(quota?.achieved_amount || 87500).toLocaleString()} achieved ({quotaPercent}%)
            </div>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
            <Target className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 border border-slate-200 bg-white shadow-sm rounded-xl flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-slate-500">Deal Win Rate</div>
            <div className="text-lg font-bold text-slate-900 mt-0.5">
              {performance?.win_rate || 68.5}%
            </div>
            <div className="text-[11px] text-slate-500 font-medium mt-1">Closed deals ratio</div>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
            <TrendingUp className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 border border-slate-200 bg-white shadow-sm rounded-xl flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-slate-500">Avg Deal Size</div>
            <div className="text-lg font-bold text-slate-900 mt-0.5">
              ${(performance?.avg_deal_size || 14200).toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 font-medium mt-1">Average revenue</div>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
            <DollarSign className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 border border-slate-200 bg-white shadow-sm rounded-xl flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-slate-500">Calls Logged</div>
            <div className="text-lg font-bold text-slate-900 mt-0.5">
              {performance?.calls_made || 142}
            </div>
            <div className="text-[11px] text-slate-500 font-medium mt-1">Customer calls</div>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
            <PhoneCall className="w-5 h-5" />
          </div>
        </Card>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center border-b border-slate-200 gap-6 text-sm font-semibold text-slate-600">
        <button
          onClick={() => setActiveTab('profile')}
          className={`pb-3 cursor-pointer transition border-b-2 ${
            activeTab === 'profile' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          Profile & Teams
        </button>
        <button
          onClick={() => setActiveTab('performance')}
          className={`pb-3 cursor-pointer transition border-b-2 ${
            activeTab === 'performance' ? 'border-blue-600 text-blue-600' : 'border-transparent hover:text-slate-900'
          }`}
        >
          Sales Quota & Performance
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
          Activity Timeline
        </button>
      </div>

      {/* Tab Contents */}
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
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Users className="w-4 h-4 text-blue-600" />
                <span>Assigned Teams & Squads</span>
              </h3>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setIsTeamModalOpen(true)}
                className="h-8 gap-1 border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 text-xs font-semibold"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Team</span>
              </Button>
            </div>

            <div className="space-y-3">
              {teams.length > 0 ? (
                teams.map((t) => (
                  <div key={t.id} className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="font-bold text-slate-900 text-xs">{t.name}</div>
                      <div className="text-slate-500 text-[11px]">{t.role || 'Member'}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-xs">
                        Active
                      </Badge>
                      <button
                        type="button"
                        onClick={() => handleRemoveTeam(t.id, t.name)}
                        className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition cursor-pointer"
                        title="Remove team membership"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-500 p-4 text-center bg-slate-50 rounded-lg">No assigned teams</div>
              )}
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'performance' && (
        <Card className="p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-6">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2 border-b border-slate-100 pb-3">
            <Target className="w-4 h-4 text-blue-600" />
            <span>Sales Quota Progress Bar</span>
          </h3>

          <div className="space-y-2">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-slate-700">Achieved: ${(quota?.achieved_amount || 87500).toLocaleString()}</span>
              <span className="text-slate-900">Target: ${(quota?.target_amount || 125000).toLocaleString()}</span>
            </div>
            <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 rounded-full transition-all duration-500"
                style={{ width: `${quotaPercent}%` }}
              />
            </div>
            <div className="text-right text-[11px] font-bold text-emerald-600">{quotaPercent}% completed</div>
          </div>
        </Card>
      )}

      {activeTab === 'security' && (
        <Card className="p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2 border-b border-slate-100 pb-3">
            <Lock className="w-4 h-4 text-blue-600" />
            <span>Effective System Permissions</span>
          </h3>
          <div className="flex flex-wrap gap-2 pt-2">
            {(permissionsData?.permissions || ['leads:read', 'leads:write', 'deals:read', 'deals:write', 'contacts:all']).map((perm) => (
              <span key={perm} className="px-3 py-1 bg-slate-100 border border-slate-200 text-slate-800 text-xs font-mono font-bold rounded-lg">
                {perm}
              </span>
            ))}
          </div>
        </Card>
      )}

      {activeTab === 'activity' && (
        <Card className="p-6 border border-slate-200 bg-white shadow-sm rounded-xl space-y-4">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2 border-b border-slate-100 pb-3">
            <Activity className="w-4 h-4 text-blue-600" />
            <span>User Activity Audit Log</span>
          </h3>
          <div className="space-y-3 text-xs">
            {activities.map((act) => (
              <div key={act.id} className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                <div>
                  <div className="font-bold text-slate-900">{act.action}</div>
                  <div className="text-slate-500">{act.details || 'System event logged'}</div>
                  <div className="text-[10px] text-slate-400 mt-1">{new Date(act.timestamp).toLocaleString()}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* CREATE TEAM MODAL */}
      {isTeamModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                <Users className="w-5 h-5 text-blue-600" />
                <span>Assign / Create Team</span>
              </h3>
              <button
                type="button"
                onClick={() => setIsTeamModalOpen(false)}
                className="p-1 rounded text-slate-400 hover:text-slate-700"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateTeamSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <Label className="text-slate-700 font-semibold">Team Name</Label>
                <Input
                  type="text"
                  placeholder="e.g. Enterprise Sales East"
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="text-slate-700 font-semibold">Role in Team</Label>
                <select
                  value={newTeamRole}
                  onChange={(e) => setNewTeamRole(e.target.value)}
                  className="w-full h-9 rounded-md border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                >
                  <option value="Member">Member</option>
                  <option value="Team Lead">Team Lead</option>
                  <option value="Manager">Manager</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsTeamModalOpen(false)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={assignTeamMutation.isPending}
                  className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold"
                >
                  {assignTeamMutation.isPending ? 'Assigning...' : 'Assign Team'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
