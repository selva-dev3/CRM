import { create } from 'zustand';

interface UIState {
  sidebarOpen: boolean;
  themeMode: 'light' | 'dark' | 'system';
  toggleSidebar: () => void;
  setThemeMode: (mode: 'light' | 'dark' | 'system') => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  themeMode: 'dark',
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setThemeMode: (mode) => set({ themeMode: mode }),
}));
