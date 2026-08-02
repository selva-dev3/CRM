export interface NavItem {
  title: string;
  href: string;
  icon: string;
  badge?: string;
}

export const navigationConfig: NavItem[] = [
  { title: 'Dashboard', href: '/dashboard', icon: 'LayoutDashboard' },
  { title: 'Leads', href: '/leads', icon: 'UserPlus' },
  { title: 'Contacts', href: '/contacts', icon: 'Users' },
  { title: 'Companies', href: '/companies', icon: 'Building2' },
  { title: 'Deals', href: '/deals', icon: 'Kanban' },
  { title: 'Tasks', href: '/tasks', icon: 'CheckSquare' },
  { title: 'Meetings', href: '/meetings', icon: 'CalendarDays' },
  { title: 'Calls', href: '/calls', icon: 'PhoneCall' },
  { title: 'Email', href: '/email', icon: 'Mail' },
  { title: 'Notes', href: '/notes', icon: 'StickyNote' },
  { title: 'Documents', href: '/documents', icon: 'FileText' },
  { title: 'Products', href: '/products', icon: 'Package' },
  { title: 'Quotes', href: '/quotes', icon: 'FileSpreadsheet' },
  { title: 'Invoices', href: '/invoices', icon: 'Receipt' },
  { title: 'Reports & Analytics', href: '/reports', icon: 'BarChart3' },
  { title: 'Calendar', href: '/calendar', icon: 'Calendar' },
  { title: 'Notifications', href: '/notifications', icon: 'Bell' },
  { title: 'User Management', href: '/users', icon: 'UserCog' },
  { title: 'Roles & Permissions', href: '/roles', icon: 'ShieldCheck' },
  { title: 'Settings', href: '/settings', icon: 'Settings' },
];
