import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import RequestDetail from '../src/pages/RequestDetail';
import { useRequest } from '../src/hooks/useIntake';

vi.mock('../src/hooks/useAuth', () => ({
  useAuth: () => ({ data: { role: 'TENANT', organization: { timezone: 'Asia/Karachi' } } }),
}));
vi.mock('../src/hooks/useIntake', () => ({
  useRequest: vi.fn(),
  useIntakeMutation: () => ({ mutate: vi.fn(), error: null }),
}));

function page() {
  return render(
    <MemoryRouter initialEntries={['/requests/request-1']}>
      <Routes>
        <Route path="/requests/:id" element={<RequestDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('request progress states', () => {
  it('shows loading while the request is being fetched', () => {
    useRequest.mockReturnValue({ isPending: true });
    page();
    expect(screen.getByRole('status')).toHaveTextContent('Loading your workspace');
  });
  it('shows active extraction progress without showing approval', () => {
    useRequest.mockReturnValue({
      isPending: false,
      data: {
        id: 'request-1',
        title: 'Leaking sink',
        status: 'PROCESSING',
        property_name: 'Cedar',
        unit_label: 'A-101',
        conversation_revision: 1,
        messages: [],
      },
    });
    page();
    expect(screen.getByRole('status')).toHaveTextContent('Processing your request');
    expect(screen.queryByText('One clear handoff.')).toBeNull();
  });
  it('shows an accessible fetch error and reload control', () => {
    useRequest.mockReturnValue({
      error: { status: 503, message: 'Please retry.' },
      refetch: vi.fn(),
    });
    page();
    expect(screen.getByRole('alert')).toHaveTextContent('Please retry.');
    expect(screen.getByRole('button', { name: 'Reload latest' })).toBeVisible();
  });
});
