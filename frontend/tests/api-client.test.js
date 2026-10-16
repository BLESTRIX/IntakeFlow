import { afterEach, expect, it, vi } from 'vitest';
import { api } from '../src/api/client';

afterEach(() => vi.unstubAllGlobals());
it('refreshes pre-login CSRF so an expired HttpOnly session can be cleared by the server', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'fresh-csrf' }) })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ csrf_token: 'session-csrf', message: 'Signed in' }),
    });
  vi.stubGlobal('fetch', fetchMock);
  await api('/auth/login', {
    method: 'POST',
    body: { email: 'tenant@example.com', password: 'password-value' },
  });
  expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/auth/csrf');
  expect(fetchMock.mock.calls[1][1].headers['X-CSRF-Token']).toBe('fresh-csrf');
  expect(fetchMock.mock.calls[1][1].credentials).toBe('same-origin');
});
