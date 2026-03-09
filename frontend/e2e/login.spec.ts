import { test, expect, DEMO_USERS } from './fixtures';

test.describe('Login Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  // -----------------------------------------------------------------------
  // Page rendering
  // -----------------------------------------------------------------------
  test('renders branding and sign-in heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'TAA' })).toBeVisible();
    await expect(page.getByText('Telco Analytics Accelerator')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  });

  test('shows demo-users tab by default', async ({ page }) => {
    const demoTab = page.getByRole('button', { name: 'Demo Users' });
    await expect(demoTab).toHaveClass(/login-mode-active/);
    await expect(page.getByText('Select a role to explore the platform')).toBeVisible();
  });

  test('displays all three demo users with correct roles', async ({ page }) => {
    for (const user of Object.values(DEMO_USERS)) {
      const btn = page.getByRole('button', { name: user.name });
      await expect(btn).toBeVisible();
      // Each button contains the user email and a role badge
      await expect(btn).toContainText(user.email);
    }

    // Verify role badges
    await expect(page.getByText('User', { exact: true })).toBeVisible();
    await expect(page.getByText('Admin', { exact: true })).toBeVisible();
    await expect(page.getByText('Management', { exact: true })).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Demo-user click login
  // -----------------------------------------------------------------------
  test('clicking Alex demo user logs in and navigates to home', async ({ page }) => {
    await page.getByRole('button', { name: DEMO_USERS.alex.name }).click();
    await page.waitForURL('/');

    // Layout header should show the user name and role badge
    await expect(page.getByText(DEMO_USERS.alex.name)).toBeVisible();
    await expect(page.locator('.role-badge')).toContainText('User');
  });

  test('clicking Sarah demo user logs in as admin', async ({ page }) => {
    await page.getByRole('button', { name: DEMO_USERS.sarah.name }).click();
    await page.waitForURL('/');

    await expect(page.getByText(DEMO_USERS.sarah.name)).toBeVisible();
    await expect(page.locator('.role-badge')).toContainText('Admin');
  });

  test('clicking Mike demo user logs in as management', async ({ page }) => {
    await page.getByRole('button', { name: DEMO_USERS.mike.name }).click();
    await page.waitForURL('/');

    await expect(page.getByText(DEMO_USERS.mike.name)).toBeVisible();
    await expect(page.locator('.role-badge')).toContainText('Management');
  });

  // -----------------------------------------------------------------------
  // Credential-based login form
  // -----------------------------------------------------------------------
  test('switching to credentials tab shows username/password form', async ({ page }) => {
    await page.getByRole('button', { name: 'Credentials' }).click();

    await expect(page.getByLabel('Username')).toBeVisible();
    await expect(page.getByLabel('Password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
    await expect(page.getByText('Demo credentials:')).toBeVisible();
  });

  test('sign-in button is disabled when fields are empty', async ({ page }) => {
    await page.getByRole('button', { name: 'Credentials' }).click();

    const signInBtn = page.getByRole('button', { name: 'Sign In' });
    await expect(signInBtn).toBeDisabled();
  });

  test('sign-in button enables after filling both fields', async ({ page }) => {
    await page.getByRole('button', { name: 'Credentials' }).click();

    await page.getByLabel('Username').fill('alex');
    await page.getByLabel('Password').fill('analyst123');

    const signInBtn = page.getByRole('button', { name: 'Sign In' });
    await expect(signInBtn).toBeEnabled();
  });

  test('can toggle between demo and credentials tabs', async ({ page }) => {
    // Start on demo tab
    await expect(page.getByText('Select a role to explore the platform')).toBeVisible();

    // Switch to credentials
    await page.getByRole('button', { name: 'Credentials' }).click();
    await expect(page.getByLabel('Username')).toBeVisible();
    await expect(page.getByText('Select a role to explore the platform')).not.toBeVisible();

    // Switch back to demo
    await page.getByRole('button', { name: 'Demo Users' }).click();
    await expect(page.getByText('Select a role to explore the platform')).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Footer text
  // -----------------------------------------------------------------------
  test('footer text matches the active mode', async ({ page }) => {
    await expect(page.getByText(/Demo authentication/)).toBeVisible();

    await page.getByRole('button', { name: 'Credentials' }).click();
    await expect(page.getByText(/JWT authentication/)).toBeVisible();
  });
});
