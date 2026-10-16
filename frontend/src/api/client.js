let csrfToken;

export class ApiError extends Error {
  constructor(data, status) {
    super(data.message || 'The request could not be completed.');
    Object.assign(this, data, { status });
  }
}

export async function csrf() {
  const response = await fetch('/api/v1/auth/csrf', { credentials: 'same-origin' });
  const data = await response.json();
  if (!response.ok) throw new ApiError(data, response.status);
  csrfToken = data.csrf_token;
  return csrfToken;
}

export async function api(path, { method = 'GET', body, key, signal } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET') {
    headers['X-CSRF-Token'] = ['/auth/login', '/auth/register'].includes(path)
      ? await csrf()
      : csrfToken || (await csrf());
  }
  if (key) headers['Idempotency-Key'] = key;
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'same-origin',
    signal,
  });
  const data = await response.json().catch(() => ({ message: 'Unexpected server response.' }));
  if (!response.ok) {
    if (data.code === 'CSRF' || response.status === 401) csrfToken = undefined;
    throw new ApiError(data, response.status);
  }
  if (data.csrf_token) csrfToken = data.csrf_token;
  if (path === '/auth/logout') csrfToken = undefined;
  return data;
}

export const newKey = () => crypto.randomUUID();
export function searchParams(values) {
  return new URLSearchParams(
    Object.entries(values).filter(([, value]) => value !== '' && value != null),
  ).toString();
}
