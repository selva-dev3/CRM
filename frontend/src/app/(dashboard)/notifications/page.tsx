'use client';

import { Input } from "@/components/ui/input";

import { ResponsiveSelect } from '@/components/common/responsive-select';
import { Textarea } from '@/components/ui/textarea';

import { getErrorMessage } from '@/lib/utils';
import React, { useState } from 'react';
import {
  Bell,
  CheckCheck,
  Trash2,
  Settings,
  Send,
  AlertCircle,
  CheckCircle2,
  X,
  Loader2,
  Radio,
  Mail,
  Smartphone,
  MessageSquare,
  Inbox
} from 'lucide-react';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { PageTabs } from '@/components/common/page-tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import {
  useNotificationsQuery,
  useUnreadCountQuery,
  useNotificationPreferencesQuery,
  useMarkAllReadMutation,
  useMarkNotificationReadMutation,
  useDeleteNotificationMutation,
  useBulkDeleteNotificationsMutation,
  useUpdateNotificationPreferencesMutation,
  useRegisterWebpushTokenMutation,
  useSendSystemAlertMutation,
  NotificationItem,
} from '@/lib/api/notifications';

export default function NotificationsPage() {
  const [activeTab, setActiveTab] = useState<'all' | 'unread'>('all');
  const [page, ] = useState(1);
  const limit = 20;

  // Selected for bulk delete
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isAlertModalOpen, setIsAlertModalOpen] = useState(false);
  const [isPreferencesModalOpen, setIsPreferencesModalOpen] = useState(false);
  const [notificationToDelete, setNotificationToDelete] = useState<NotificationItem | null>(null);

  // System Alert form states
  const [alertTitle, setAlertTitle] = useState('');
  const [alertMessage, setAlertMessage] = useState('');

  // Preferences form states
  const [prefEmail, setPrefEmail] = useState(true);
  const [prefWebpush, setPrefWebpush] = useState(true);
  const [prefSlack, setPrefSlack] = useState(false);
  const [prefDigest, setPrefDigest] = useState('Daily');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const { data: notifications = [], isLoading: isNotificationsLoading } = useNotificationsQuery({
    page,
    limit,
    unread_only: activeTab === 'unread',
  });

  const { data: unreadData } = useUnreadCountQuery();
  const { data: preferences } = useNotificationPreferencesQuery();

  // Mutations
  const markAllReadMutation = useMarkAllReadMutation();
  const markReadMutation = useMarkNotificationReadMutation();
  const deleteMutation = useDeleteNotificationMutation();
  const bulkDeleteMutation = useBulkDeleteNotificationsMutation();
  const updatePrefsMutation = useUpdateNotificationPreferencesMutation();
  const registerWebpushMutation = useRegisterWebpushTokenMutation();
  const sendAlertMutation = useSendSystemAlertMutation();

  const handleMarkAllRead = async () => {
    try {
      await markAllReadMutation.mutateAsync();
      setSuccessMessage('All notifications marked as read.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to mark all as read.'));
    }
  };

  const handleMarkSingleRead = async (id: string) => {
    try {
      await markReadMutation.mutateAsync(id);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to mark notification read.'));
    }
  };

  const handleDeleteSingle = async () => {
    if (!notificationToDelete) return;
    try {
      await deleteMutation.mutateAsync(notificationToDelete.id);
      setSuccessMessage('Notification deleted.');
      setNotificationToDelete(null);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete notification.'));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} notification(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete selected notifications.'));
    }
  };

  const handleOpenPreferencesModal = () => {
    if (preferences) {
      setPrefEmail(preferences.email_notifications);
      setPrefWebpush(preferences.webpush_notifications);
      setPrefSlack(preferences.slack_notifications);
      setPrefDigest(preferences.digest_frequency || 'Daily');
    }
    setIsPreferencesModalOpen(true);
  };

  const handleSavePreferencesSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await updatePrefsMutation.mutateAsync({
        email_notifications: prefEmail,
        webpush_notifications: prefWebpush,
        slack_notifications: prefSlack,
        digest_frequency: prefDigest,
      });
      setSuccessMessage('Notification delivery preferences updated successfully.');
      setIsPreferencesModalOpen(false);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to update preferences.'));
    }
  };

  const handleRegisterWebpush = async () => {
    try {
      const dummyToken = `webpush_token_${Math.random().toString(36).substring(2, 10)}`;
      const res = await registerWebpushMutation.mutateAsync({ token: dummyToken, device_type: 'Chrome Desktop' });
      setSuccessMessage(res.message || 'WebPush browser token registered for push notifications.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to register WebPush token.'));
    }
  };

  const handleSendAlertSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!alertTitle.trim() || !alertMessage.trim()) return;
    try {
      const res = await sendAlertMutation.mutateAsync({ title: alertTitle.trim(), message: alertMessage.trim() });
      setSuccessMessage(res.message || 'System alert broadcasted to all users.');
      setIsAlertModalOpen(false);
      setAlertTitle('');
      setAlertMessage('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send system alert.'));
    }
  };

  const toggleSelectNotification = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedIds(next);
  };

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Toast Feedback */}
      {successMessage && (
        <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span className="truncate max-w-2xl">{successMessage}</span>
          </div>
          <button type="button" aria-label="Dismiss success message" onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center justify-between p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
          <button type="button" aria-label="Dismiss error message" onClick={() => setErrorMessage(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Bell className="w-7 h-7 text-indigo-600" />
            Notification Center & Alerts
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Real-time activity alerts, WebPush browser notifications, and delivery preferences</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleMarkAllRead}
            disabled={markAllReadMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer disabled:opacity-50"
          >
            {markAllReadMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCheck className="w-4 h-4 text-emerald-600" />}
            Mark All Read
          </button>

          <button
            onClick={handleRegisterWebpush}
            disabled={registerWebpushMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer disabled:opacity-50"
          >
            {registerWebpushMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Radio className="w-4 h-4 text-purple-600" />}
            Register WebPush
          </button>

          <button
            onClick={() => setIsAlertModalOpen(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-3.5 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <Send className="w-4 h-4" />
            Broadcast Alert
          </button>

          <button
            onClick={handleOpenPreferencesModal}
            className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-3.5 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <Settings className="w-4 h-4 text-slate-300" />
            Preferences
          </button>
        </div>
      </div>



      {/* Notifications Feed Container */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden space-y-4 p-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-slate-100">
          <PageTabs
            value={activeTab}
            onValueChange={setActiveTab}
            variant="default"
            className="w-auto"
            tabs={[
              { value: 'all', label: `All Notifications (${notifications.length})` },
              { value: 'unread', label: `Unread Only (${unreadData?.unread_count ?? notifications.filter((notification) => !notification.is_read).length})` },
            ]}
            listClassName="bg-slate-100"
            triggerClassName="text-xs font-bold data-[state=active]:bg-indigo-600 data-[state=active]:text-white"
          />

          {selectedIds.size > 0 && (
            <div className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1 sm:w-auto">
              <span className="text-xs font-semibold text-indigo-700">{selectedIds.size} selected</span>
              <button
                onClick={handleBulkDelete}
                className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold cursor-pointer"
              >
                Bulk Delete
              </button>
            </div>
          )}
        </div>

        {/* Notifications List */}
        {isNotificationsLoading ? (
          <div className="flex items-center justify-center py-12 text-slate-500 gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
            <span className="text-xs font-medium">Loading notification activity feed...</span>
          </div>
        ) : notifications.length === 0 ? (
          <div className="text-center py-12 space-y-2">
            <Inbox className="w-10 h-10 text-slate-300 mx-auto" />
            <h4 className="text-sm font-bold text-slate-700">No notifications found</h4>
            <p className="text-xs text-slate-400">You are all caught up on system updates & lead activity!</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {notifications.map((n) => (
              <div
                key={n.id}
                onClick={() => handleMarkSingleRead(n.id)}
                className={`p-4 rounded-xl transition-colors flex items-start justify-between gap-4 cursor-pointer ${
                  !n.is_read ? 'bg-indigo-50/40 border border-indigo-100/60' : 'hover:bg-slate-50'
                }`}
              >
                <div className="flex items-start gap-3.5">
                  <Checkbox
                    checked={selectedIds.has(n.id)}
                    onClick={(event) => event.stopPropagation()}
                    onCheckedChange={() => {
                      toggleSelectNotification(n.id);
                    }}
                    aria-label={`Select notification: ${n.title || 'System Notification'}`}
                    className="mt-1 h-4 w-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500"
                  />

                  <div className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 ${!n.is_read ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                    <Bell className="w-4 h-4" />
                  </div>

                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-bold text-slate-900">{n.title || 'System Notification'}</h4>
                      {!n.is_read && (
                        <span className="h-2 w-2 rounded-full bg-indigo-600 inline-block animate-pulse" />
                      )}
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed">{n.message}</p>
                    <span className="text-[11px] text-slate-400 block pt-1 font-mono">
                      {n.created_at ? n.created_at.substring(0, 16) : 'Just now'}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                  {!n.is_read && (
                    <button
                      onClick={() => handleMarkSingleRead(n.id)}
                      title="Mark as read"
                      className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                    </button>
                  )}

                  <button
                    onClick={() => setNotificationToDelete(n)}
                    title="Delete notification"
                    className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Broadcast System Alert Modal */}
      {isAlertModalOpen && (
        <ModalShell
          isOpen={isAlertModalOpen}
          onClose={() => setIsAlertModalOpen(false)}
          size="md"
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Send className="w-5 h-5 text-indigo-600" />
              Broadcast System Alert
            </h3>
          }
        >
          <form onSubmit={handleSendAlertSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Alert Title *</label>
              <Input
                type="text"
                required
                value={alertTitle}
                onChange={(e) => setAlertTitle(e.target.value)}
                placeholder="e.g. Scheduled System Maintenance"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Alert Message *</label>
              <Textarea
                required
                rows={3}
                value={alertMessage}
                onChange={(e) => setAlertMessage(e.target.value)}
                placeholder="e.g. System upgrade will occur tonight at 02:00 UTC."
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
              <button type="button" onClick={() => setIsAlertModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={sendAlertMutation.isPending}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {sendAlertMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Broadcast Alert
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Delivery Preferences Modal */}
      {isPreferencesModalOpen && (
        <ModalShell
          isOpen={isPreferencesModalOpen}
          onClose={() => setIsPreferencesModalOpen(false)}
          size="md"
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Settings className="w-5 h-5 text-slate-700" />
              Notification Delivery Preferences
            </h3>
          }
        >
          <form onSubmit={handleSavePreferencesSubmit} className="space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
                  <Mail className="w-4 h-4 text-indigo-600" />
                  <span>Email Notifications</span>
                </div>
                <Switch
                  checked={prefEmail}
                  onCheckedChange={setPrefEmail}
                  aria-label="Enable email notifications"
                />
              </div>

              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
                  <Smartphone className="w-4 h-4 text-purple-600" />
                  <span>WebPush Browser Push Alerts</span>
                </div>
                <Switch
                  checked={prefWebpush}
                  onCheckedChange={setPrefWebpush}
                  aria-label="Enable browser push notifications"
                />
              </div>

              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
                  <MessageSquare className="w-4 h-4 text-emerald-600" />
                  <span>Slack Channel Webhook Alerts</span>
                </div>
                <Switch
                  checked={prefSlack}
                  onCheckedChange={setPrefSlack}
                  aria-label="Enable Slack notifications"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Email Digest Frequency</label>
              <ResponsiveSelect
                value={prefDigest}
                onValueChange={setPrefDigest}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="Realtime">Realtime Immediate</option>
                <option value="Daily">Daily Digest</option>
                <option value="Weekly">Weekly Summary</option>
              </ResponsiveSelect>
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
              <button type="button" onClick={() => setIsPreferencesModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={updatePrefsMutation.isPending}
                className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {updatePrefsMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Save Preferences
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Confirm Delete Modal */}
      {notificationToDelete && (
        <ConfirmModal
          isOpen={!!notificationToDelete}
          title="Delete Notification"
          description={`Are you sure you want to delete this notification?`}
          confirmText="Delete Alert"
          variant="danger"
          onConfirm={handleDeleteSingle}
          onClose={() => setNotificationToDelete(null)}
        />
      )}
    </div>
  );
}
