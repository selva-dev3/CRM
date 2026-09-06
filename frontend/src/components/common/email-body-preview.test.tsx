import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { EmailBodyPreview, formatEmailBody } from './email-body-preview';

describe('EmailBodyPreview', () => {
  it('turns stored email HTML into readable text', () => {
    const body = '<p>Hello Selvakumar,</p><p>Quote QUO-2026-000013: INR 10000.</p><p><a href="https://example.test/review?a=1&amp;b=2">Review your quote</a></p>';
    render(
      <EmailBodyPreview body={body} />,
    );

    expect(formatEmailBody(body)).toBe(
      'Hello Selvakumar,\nQuote QUO-2026-000013: INR 10000.\nReview your quote',
    );
    expect(screen.getByText(/Hello Selvakumar,/)).toBeInTheDocument();
    expect(screen.queryByText(/<p>/)).not.toBeInTheDocument();
  });

  it('decodes common and numeric HTML entities', () => {
    expect(formatEmailBody('Terms &amp; Conditions &#8377;5000 &#x2713;')).toBe(
      'Terms & Conditions ₹5000 ✓',
    );
  });

  it('removes executable and style content instead of rendering it', () => {
    render(
      <EmailBodyPreview
        body={'<p>Safe message</p><script>alert("unsafe")</script><style>p{display:none}</style>'}
      />,
    );

    expect(screen.getByText('Safe message')).toBeInTheDocument();
    expect(screen.queryByText(/unsafe/)).not.toBeInTheDocument();
    expect(document.querySelector('script')).not.toBeInTheDocument();
  });

  it('provides an explicit fallback for an empty body', () => {
    render(<EmailBodyPreview body="  " />);
    expect(screen.getByText('No preview body.')).toBeInTheDocument();
  });
});
