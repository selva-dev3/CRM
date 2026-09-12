import { describe, expect, it } from 'vitest';
import {
  filterNavigationSections,
  getRoutePermission,
  navigationSections,
  protectedRoutes,
  type NavSection,
} from './navigation';
import { PERMISSIONS } from '@/lib/permissions';

const sections: NavSection[] = [
  {
    items: [{ title: 'Dashboard', href: '/dashboard', icon: 'LayoutDashboard', permission: PERMISSIONS.DASHBOARD.READ }],
  },
  {
    title: 'CRM',
    items: [
      { title: 'Leads', href: '/leads', icon: 'UserPlus', permission: PERMISSIONS.LEADS.READ },
      { title: 'Contacts', href: '/contacts', icon: 'Users', permission: PERMISSIONS.CONTACTS.READ },
    ],
  },
  {
    title: 'Administration',
    items: [
      { title: 'User Management', href: '/users', icon: 'UserCog', permission: PERMISSIONS.USERS.READ },
    ],
  },
];

describe('filterNavigationSections', () => {
  it('keeps items whose permission is held', () => {
    const result = filterNavigationSections(sections, [PERMISSIONS.DASHBOARD.READ, PERMISSIONS.LEADS.READ]);
    expect(result.map((s) => s.items.map((i) => i.title))).toEqual([['Dashboard'], ['Leads']]);
  });

  it('drops sections left with zero visible items', () => {
    const result = filterNavigationSections(sections, [PERMISSIONS.DASHBOARD.READ]);
    const titles = result.map((s) => s.items.map((i) => i.title));
    expect(titles).toEqual([['Dashboard']]);
  });

  it('keeps an item without a permission requirement visible to everyone', () => {
    const open: NavSection[] = [
      { items: [{ title: 'Dashboard', href: '/dashboard', icon: 'LayoutDashboard' }] },
    ];
    expect(filterNavigationSections(open, []).length).toBe(1);
  });

  it('does not grant navigation access for the legacy "all" sentinel', () => {
    const result = filterNavigationSections(sections, ['all']);
    expect(result).toEqual([]);
  });
});

describe('getRoutePermission', () => {
  it('returns undefined for unguarded paths', () => {
    expect(getRoutePermission('')).toBeUndefined();
    expect(getRoutePermission('/')).toBeUndefined();
    expect(getRoutePermission('/unknown-page')).toBeUndefined();
  });

  it('maps top-level routes to their required permission', () => {
    expect(getRoutePermission('/leads')).toBe(PERMISSIONS.LEADS.READ);
    expect(getRoutePermission('/settings')).toBe(PERMISSIONS.SETTINGS.READ);
    expect(getRoutePermission('/organization')).toBe(PERMISSIONS.ORGANIZATION.READ);
    expect(getRoutePermission('/integrations')).toBe(PERMISSIONS.INTEGRATIONS.READ);
    expect(getRoutePermission('/notifications')).toBe(PERMISSIONS.NOTIFICATIONS.READ);
    expect(getRoutePermission('/users')).toBe(PERMISSIONS.USERS.READ);
    expect(getRoutePermission('/roles')).toBe(PERMISSIONS.ROLES.READ);
    expect(getRoutePermission('/ai')).toBe(PERMISSIONS.AI.READ);
    expect(getRoutePermission('/whatsapp')).toEqual([
      PERMISSIONS.WHATSAPP.READ_ASSIGNED,
      PERMISSIONS.WHATSAPP.READ_ALL,
    ]);
    expect(getRoutePermission('/projects')).toBe(PERMISSIONS.PROJECTS.READ);
  });

  it('groups working modules into the professional product sections', () => {
    const byTitle = Object.fromEntries(
      navigationSections.filter((section) => section.title).map((section) => [section.title, section.items.map((item) => item.title)]),
    );

    expect(byTitle.CRM).toContain('Calendar');
    expect(byTitle.CRM).not.toContain('Products');
    expect(byTitle.Sales).toEqual(['Products', 'Quotes', 'Invoices', 'Payments']);
    expect(byTitle.Projects).toEqual(['Projects']);
    expect(byTitle.Analytics).not.toContain('Calendar');
    expect(byTitle.Administration).toEqual([
      'User Management',
      'Roles & Permissions',
      'Integrations',
      'Settings',
    ]);
  });

  it('shows WhatsApp navigation to read-all-only roles', () => {
    const visible = filterNavigationSections(navigationSections, [PERMISSIONS.WHATSAPP.READ_ALL]);
    expect(visible.flatMap((section) => section.items).map((item) => item.href)).toContain('/whatsapp');
  });

  it('lets detail routes inherit the parent permission', () => {
    expect(getRoutePermission('/leads/123')).toBe(PERMISSIONS.LEADS.READ);
    expect(getRoutePermission('/users/42/edit')).toBe(PERMISSIONS.USERS.READ);
  });

  it('is case-insensitive', () => {
    expect(getRoutePermission('/Leads')).toBe(PERMISSIONS.LEADS.READ);
  });
});

describe('navigation/route consistency', () => {
  it('registers every sidebar destination in the protected route map with a matching permission', () => {
    for (const section of navigationSections) {
      for (const item of section.items) {
        const segment = item.href.split('/').filter(Boolean)[0];
        expect(protectedRoutes[segment]).toBeDefined();
        expect(protectedRoutes[segment]).toEqual(item.permission);
      }
    }
  });
});
