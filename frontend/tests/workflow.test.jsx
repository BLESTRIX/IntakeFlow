import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { api } from '../src/api/client';
import NewRequest from '../src/pages/NewRequest';
import ReviewedDraft from '../src/features/review/ReviewedDraft';
import { ErrorPanel, EvidenceReference } from '../src/components/ui';
import { Navigation } from '../src/layouts/AppLayout';
import { activeRequest } from '../src/hooks/useIntake';

vi.mock('../src/api/client', () => ({ api: vi.fn(), newKey: () => 'test-operation' }));

function wrap(component) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
        })
      }
    >
      <MemoryRouter>{component}</MemoryRouter>
    </QueryClientProvider>,
  );
}
const request = {
  id: 'request-1',
  status: 'NEEDS_REVIEW',
  conversation_revision: 3,
  draft_version: 2,
  draft_stale: false,
  approval_missing: [],
  property_name: 'Cedar',
  unit_label: 'A-101',
  draft: {
    version: 2,
    source_revision: 3,
    data: {
      category: 'PLUMBING',
      room_or_area: 'kitchen',
      affected_item: 'sink',
      description: 'The sink leaks underneath.',
      priority: 'ROUTINE',
      assigned_team: 'Plumbing team',
      multiple_issues_resolved: false,
    },
  },
};

beforeEach(() => {
  api.mockReset();
  api.mockImplementation((path) =>
    Promise.resolve(
      path.startsWith('/units')
        ? { total: 1, items: [{ id: 'unit-1', label: 'A-101', property_name: 'Cedar' }] }
        : path.endsWith('/draft')
          ? { history: [], corrections: [] }
          : { items: [] },
    ),
  );
});

describe('tenant intake', () => {
  it('validates required fields before submission', async () => {
    wrap(<NewRequest />);
    await screen.findByLabelText('Short title');
    await userEvent.click(screen.getByRole('button', { name: /submit request/i }));
    expect(await screen.findByText('Select your assigned unit')).toBeVisible();
    expect(screen.getByText('Give the issue a short title')).toBeVisible();
    expect(screen.getByText('Describe the maintenance issue')).toBeVisible();
    expect(api.mock.calls.filter(([, opts]) => opts?.method === 'POST')).toHaveLength(0);
  });
  it('polls only active processing or pending commands', () => {
    expect(activeRequest({ status: 'PROCESSING' })).toBe(true);
    expect(activeRequest({ status: 'NEEDS_REVIEW', pending_command_id: 'cmd' })).toBe(true);
    expect(activeRequest({ status: 'WAITING_FOR_TENANT' })).toBe(false);
    expect(activeRequest({ status: 'APPROVED' })).toBe(false);
  });
});

describe('review workspace', () => {
  it('links exact evidence without executing source HTML', () => {
    wrap(
      <EvidenceReference
        evidence={{ field: 'symptoms', message_id: 'source-1', quote: '<script>bad()</script>' }}
      />,
    );
    expect(screen.getByRole('link')).toHaveAttribute('href', '#message-source-1');
    expect(screen.getByText('<script>bad()</script>')).toBeVisible();
    expect(document.querySelector('script')).toBeNull();
  });
  it('submits corrections with both expected revisions', async () => {
    wrap(<ReviewedDraft request={request} />);
    const area = screen.getByLabelText('Affected room / area');
    await userEvent.clear(area);
    await userEvent.type(area, 'laundry room');
    expect(screen.getByRole('button', { name: 'Approve work order' })).toBeDisabled();
    api.mockImplementation((path, opts) =>
      opts?.method === 'PATCH'
        ? Promise.resolve({ data: opts.body.values, version: 3, source_revision: 3 })
        : Promise.resolve({ history: [], corrections: [], items: [] }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Save reviewed draft' }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        '/requests/request-1/draft',
        expect.objectContaining({
          method: 'PATCH',
          body: expect.objectContaining({
            expected_version: 2,
            source_revision: 3,
            values: expect.objectContaining({ room_or_area: 'laundry room' }),
          }),
        }),
      ),
    );
  });
  it('shows a conflict and preserves unsaved corrections', async () => {
    wrap(<ReviewedDraft request={request} />);
    await userEvent.type(screen.getByLabelText('Affected room / area'), ' corner');
    api.mockRejectedValueOnce(
      Object.assign(new Error('Reload the latest review.'), { status: 409 }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Save reviewed draft' }));
    expect(await screen.findByText('This review has changed.')).toBeVisible();
    expect(screen.getByLabelText('Affected room / area')).toHaveValue('kitchen corner');
  });
  it('shows permission and server errors accessibly', () => {
    wrap(<ErrorPanel error={{ status: 403, message: 'Staff access required' }} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Permission denied');
  });
});

it('limits tenant navigation to tenant pages', () => {
  wrap(<Navigation user={{ role: 'TENANT' }} />);
  expect(screen.getByRole('link', { name: 'My requests' })).toBeVisible();
  expect(screen.queryByRole('link', { name: 'AI usage' })).toBeNull();
  expect(screen.queryByRole('link', { name: 'People & assignments' })).toBeNull();
});
