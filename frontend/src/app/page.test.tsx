import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import LandingPage from './page';

describe('LandingPage', () => {
  it('shows the reference hero and uses working authentication links', () => {
    render(<LandingPage />);

    expect(screen.getByRole('heading', { name: /Turn Leads into Lasting Relationships/i })).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Sign in' })[0]).toHaveAttribute('href', '/login');
    expect(screen.getAllByRole('link', { name: /Get Started/i })[0]).toHaveAttribute('href', '/register');
    expect(screen.getByRole('img', { name: /Mivaro CRM preview/i })).toHaveAttribute('src', expect.stringContaining('landingbackground1.jpeg'));
  });

  it('provides destinations for every primary navigation item', () => {
    render(<LandingPage />);

    const nav = screen.getByRole('navigation', { name: 'Primary navigation' });
    for (const item of ['Product', 'Solutions', 'Pricing', 'Resources', 'About']) {
      const link = nav.querySelector(`a[href="#${item.toLowerCase()}"]`);
      expect(link).not.toBeNull();
      expect(document.getElementById(item.toLowerCase())).not.toBeNull();
    }
  });
});
