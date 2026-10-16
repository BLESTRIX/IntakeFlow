import { test, expect } from '@playwright/test';

async function login(page, role) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(`${role}@demo.intakeflow.app`);
  await page.getByLabel('Password', { exact: true }).fill('IntakeFlow-demo-2026!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'A little clarity. A better day.' }),
  ).toBeVisible();
}

test('clarify, preserve corrections, approve exactly one work order, show tenant status', async ({
  browser,
}) => {
  const baseURL = test.info().project.use.baseURL;
  const tenantContext = await browser.newContext({ baseURL });
  const staffContext = await browser.newContext({ baseURL });
  const tenant = await tenantContext.newPage();
  const staff = await staffContext.newPage();
  await login(tenant, 'tenant');
  await tenant.goto('/app/requests/new');
  await tenant.getByLabel('Property and unit').selectOption({ label: 'Cedar Residences · A-101' });
  const title = `E2E leaking sink ${Date.now()}`;
  await tenant.getByLabel('Short title').fill(title);
  await tenant
    .getByLabel('What’s happening?')
    .fill('The sink has been leaking since yesterday and the cupboard underneath is wet.');
  await tenant.getByRole('button', { name: 'Submit request' }).click();
  await expect(tenant).toHaveURL(/\/app\/requests\/[a-f0-9-]+$/);
  const requestPath = new URL(tenant.url()).pathname;
  const requestId = requestPath.split('/').at(-1);
  await expect(tenant.locator('.request-heading .status-badge')).toHaveText('Needs review');
  await login(staff, 'staff');
  await staff.goto(requestPath);
  await expect(staff.getByText('Which room or area is affected?', { exact: true })).toBeVisible();
  await staff
    .getByLabel('Your clarification question or rejection reason')
    .fill('Which room is the leaking sink in?');
  await staff.getByRole('button', { name: 'Send clarification' }).click();
  await expect(staff.locator('.request-heading .status-badge')).toHaveText('Waiting for tenant');
  await tenant.reload();
  await expect(
    tenant.getByText('Which room is the leaking sink in?', { exact: true }),
  ).toBeVisible();
  await tenant.getByLabel('Your reply').fill('The sink is in the kitchen.');
  await tenant.getByRole('button', { name: 'Send reply' }).click();
  await expect(tenant.locator('.request-heading .status-badge')).toHaveText('Needs review');
  await staff.reload();
  await expect(staff.getByLabel('Extraction revision')).toContainText('Conversation revision 3');
  await staff.getByLabel('Affected room / area').fill('kitchen');
  await staff
    .getByLabel('Useful problem description')
    .fill('The kitchen sink leaks into the cupboard underneath.');
  await staff.getByLabel('Staff-selected priority').selectOption('PRIORITY');
  await staff
    .getByLabel('Correction reason (optional)')
    .fill('Location verified from the tenant reply; description reviewed.');
  await staff.getByRole('button', { name: 'Save reviewed draft' }).click();
  await expect(staff.getByRole('button', { name: 'Approve work order' })).toBeEnabled();
  await staff.getByRole('button', { name: 'Approve work order' }).click();
  await staff.getByRole('button', { name: 'Confirm approval' }).click();
  await expect(staff.locator('.request-heading .status-badge')).toHaveText('Approved');
  await expect(staff.getByRole('link', { name: 'View work order', exact: true })).toBeVisible();
  const orders = await staff.request.get('/api/v1/work-orders?page_size=100');
  expect(
    (await orders.json()).items.filter((order) => order.request_id === requestId),
  ).toHaveLength(1);
  await tenant.reload();
  await tenant.getByRole('link', { name: 'View work order', exact: true }).click();
  await expect(tenant.locator('.page-heading .status-badge')).toHaveText('Open');
  await expect(
    tenant.getByText('The kitchen sink leaks into the cupboard underneath.', { exact: true }),
  ).toBeVisible();
  await tenantContext.close();
  await staffContext.close();
});

test('landing and tenant navigation fit a small screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /From “something’s/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await login(page, 'tenant');
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await expect(page.getByRole('link', { name: 'My requests', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'People & assignments', exact: true })).toHaveCount(
    0,
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});

test('admin directories, usage, and audit pages load', async ({ page }) => {
  await login(page, 'admin');
  await page.goto('/app/admin/properties');
  await expect(
    page.getByRole('heading', { name: 'Properties & units', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Cedar Residences', exact: true })).toBeVisible();
  await page.goto('/app/admin/members');
  await expect(
    page.getByRole('heading', { name: 'Organization members', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('admin@demo.intakeflow.app', { exact: true })).toBeVisible();
  await page.goto('/app/admin/usage');
  await expect(page.getByRole('heading', { name: 'Model invocations', exact: true })).toBeVisible();
  await page.goto('/app/admin/audit');
  await expect(page.getByText('request.submitted', { exact: true }).first()).toBeVisible();
});
