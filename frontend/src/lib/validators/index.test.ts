import { describe, expect, it } from 'vitest';
import { registerSchema } from './index';

describe('registerSchema', () => {
  const validRegistration = {
    name: 'Alex',
    email: 'alex@crm.com',
    password: 'password123',
    organizationName: 'Acme',
  };

  it('rejects passwords shorter than eight characters', () => {
    const result = registerSchema.safeParse({
      ...validRegistration,
      password: 'short7',
    });

    expect(result.success).toBe(false);
  });

  it('accepts an eight-character password', () => {
    const result = registerSchema.safeParse({
      ...validRegistration,
      password: '12345678',
    });

    expect(result.success).toBe(true);
  });
});
