export interface NavItem {
  title: string;
  href: string;
  icon: string;
  badge?: string;
  permission?: string;
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

export const navigationSections: NavSection[] = [
  {
    items: [
      { title: 'Dashboard', href: '/dashboard', icon: 'LayoutDashboard', permission: 'dashboard:read' }
    ]
  },
  {
    title: 'CRM',
    items: [
      { title: 'Leads', href: '/leads', icon: 'UserPlus', permission: 'leads:read' },
      { title: 'Contacts', href: '/contacts', icon: 'Users', permission: 'contacts:read' },
      { title: 'Companies', href: '/companies', icon: 'Building2', permission: 'companies:read' },
      { title: 'Deals', href: '/deals', icon: 'Kanban', permission: 'deals:read' },
      { title: 'Tasks', href: '/tasks', icon: 'CheckSquare', permission: 'tasks:read' },
      { title: 'Meetings', href: '/meetings', icon: 'CalendarDays', permission: 'meetings:read' },
      { title: 'Calls', href: '/calls', icon: 'PhoneCall', permission: 'calls:read' },
      { title: 'Emails', href: '/email', icon: 'Mail', permission: 'emails:read' },
      { title: 'Notes', href: '/notes', icon: 'StickyNote', permission: 'notes:read' },
      { title: 'Documents', href: '/documents', icon: 'FileText', permission: 'documents:read' },
      { title: 'Products', href: '/products', icon: 'Package', permission: 'products:read' },
      { title: 'Quotes', href: '/quotes', icon: 'FileSpreadsheet', permission: 'quotes:read' },
      { title: 'Invoices', href: '/invoices', icon: 'Receipt', permission: 'invoices:read' }
    ]
  },
  {
    title: 'Analytics',
    items: [
      { title: 'Reports', href: '/reports', icon: 'BarChart3', permission: 'reports:read' },
      { title: 'Calendar', href: '/calendar', icon: 'Calendar', permission: 'calendar:read' }
    ]
  },
  {
    title: 'Administration',
    items: [
      { title: 'User Management', href: '/users', icon: 'UserCog', permission: 'users:read' },
      { title: 'Roles & Permissions', href: '/roles', icon: 'ShieldCheck', permission: 'roles:read' }
    ]
  }
];

export const navigationConfig: NavItem[] = navigationSections.flatMap((s) => s.items);
