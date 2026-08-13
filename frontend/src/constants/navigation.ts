export interface NavItem {
  title: string;
  href: string;
  icon: string;
  badge?: string;
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

export const navigationSections: NavSection[] = [
  {
    items: [
      { title: 'Dashboard', href: '/dashboard', icon: 'LayoutDashboard' }
    ]
  },
  {
    title: 'CRM',
    items: [
      { title: 'Leads', href: '/leads', icon: 'UserPlus' },
      { title: 'Contacts', href: '/contacts', icon: 'Users' },
      { title: 'Companies', href: '/companies', icon: 'Building2' },
      { title: 'Deals', href: '/deals', icon: 'Kanban' },
      { title: 'Tasks', href: '/tasks', icon: 'CheckSquare' },
      { title: 'Meetings', href: '/meetings', icon: 'CalendarDays' },
      { title: 'Calls', href: '/calls', icon: 'PhoneCall' },
      { title: 'Emails', href: '/email', icon: 'Mail' },
      { title: 'Notes', href: '/notes', icon: 'StickyNote' },
      { title: 'Documents', href: '/documents', icon: 'FileText' },
      { title: 'Products', href: '/products', icon: 'Package' },
      { title: 'Quotes', href: '/quotes', icon: 'FileSpreadsheet' },
      { title: 'Invoices', href: '/invoices', icon: 'Receipt' }
    ]
  },
  {
    title: 'Analytics',
    items: [
      { title: 'Reports', href: '/reports', icon: 'BarChart3' },
      { title: 'Calendar', href: '/calendar', icon: 'Calendar' }
    ]
  },
  {
    title: 'Administration',
    items: [
      { title: 'User Management', href: '/users', icon: 'UserCog' },
      { title: 'Roles & Permissions', href: '/roles', icon: 'ShieldCheck' }
    ]
  }
];

export const navigationConfig: NavItem[] = navigationSections.flatMap((s) => s.items);
