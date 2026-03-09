import { test, expect, DEMO_USERS, loginAsDemoUser } from './fixtures';

test.describe('Navigation & Route Guards', () => {
  // -----------------------------------------------------------------------
  // Unauthenticated redirects
  // -----------------------------------------------------------------------
  test('unauthenticated user is redirected to /login from home', async ({ page }) => {
    await page.goto('/');
    await page.waitForURL('/login');
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  });

  test('unauthenticated user is redirected to /login from /generate', async ({ page }) => {
    await page.goto('/generate');
    await page.waitForURL('/login');
  });

  test('unauthenticated user is redirected to /login from /domains', async ({ page }) => {
    await page.goto('/domains');
    await page.waitForURL('/login');
  });

  test('unauthenticated user is redirected to /login from /compliance', async ({ page }) => {
    await page.goto('/compliance');
    await page.waitForURL('/login');
  });

  test('unauthenticated user is redirected to /login from /users', async ({ page }) => {
    await page.goto('/users');
    await page.waitForURL('/login');
  });

  // -----------------------------------------------------------------------
  // Sidebar navigation (authenticated as Alex - user role)
  // -----------------------------------------------------------------------
  test('sidebar contains expected nav items for user role', async ({ authedPage: page }) => {
    const sidebar = page.locator('.app-sidebar');

    // Items visible to all authenticated users
    await expect(sidebar.getByText('Home')).toBeVisible();
    await expect(sidebar.getByText('Generate')).toBeVisible();
    await expect(sidebar.getByText('Domains')).toBeVisible();
    await expect(sidebar.getByText('Lineage')).toBeVisible();
    await expect(sidebar.getByText('Compliance')).toBeVisible();
    await expect(sidebar.getByText('Analytics')).toBeVisible();
    await expect(sidebar.getByText('Costs')).toBeVisible();

    // Items gated by permissions that 'user' role does NOT have
    await expect(sidebar.getByText('Schema Import')).not.toBeVisible();
    await expect(sidebar.getByText('Users')).not.toBeVisible();
  });

  test('sidebar shows Schema Import and Users for admin role', async ({ adminPage: page }) => {
    const sidebar = page.locator('.app-sidebar');
    await expect(sidebar.getByText('Schema Import')).toBeVisible();
    // admin does NOT have users:manage -- only management does
    await expect(sidebar.getByText('Users')).not.toBeVisible();
  });

  test('sidebar shows all nav items for management role', async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await loginAsDemoUser(page, DEMO_USERS.mike);

    const sidebar = page.locator('.app-sidebar');
    await expect(sidebar.getByText('Schema Import')).toBeVisible();
    await expect(sidebar.getByText('Users')).toBeVisible();

    await ctx.close();
  });

  test('clicking sidebar links navigates to correct pages', async ({ authedPage: page }) => {
    const sidebar = page.locator('.app-sidebar');

    // Navigate to Generate
    await sidebar.getByText('Generate').click();
    await page.waitForURL('/generate');
    await expect(page.getByRole('heading', { name: 'Generate Artefacts' })).toBeVisible();

    // Navigate to Domains
    await sidebar.getByText('Domains').click();
    await page.waitForURL('/domains');
    await expect(page.getByRole('heading', { name: 'Domain Explorer' })).toBeVisible();

    // Navigate to Compliance
    await sidebar.getByText('Compliance').click();
    await page.waitForURL('/compliance');
    await expect(page.getByRole('heading', { name: 'Compliance Assessment' })).toBeVisible();

    // Navigate to Analytics
    await sidebar.getByText('Analytics').click();
    await page.waitForURL('/analytics');

    // Navigate back Home
    await sidebar.getByText('Home').click();
    await page.waitForURL('/');
    await expect(page.getByRole('heading', { name: 'Telco Analytics Accelerator' })).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Active nav-item highlight
  // -----------------------------------------------------------------------
  test('active sidebar link has the "active" class', async ({ authedPage: page }) => {
    // Home should be active initially
    const homeLink = page.locator('.app-sidebar .nav-item', { hasText: 'Home' });
    await expect(homeLink).toHaveClass(/active/);

    // Navigate to Domains
    await page.locator('.app-sidebar').getByText('Domains').click();
    await page.waitForURL('/domains');

    const domainsLink = page.locator('.app-sidebar .nav-item', { hasText: 'Domains' });
    await expect(domainsLink).toHaveClass(/active/);
    await expect(homeLink).not.toHaveClass(/active/);
  });

  // -----------------------------------------------------------------------
  // Logout
  // -----------------------------------------------------------------------
  test('clicking Sign Out returns to login page', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: 'Sign Out' }).click();
    await page.waitForURL('/login');
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  });

  test('after logout, navigating to / redirects to /login', async ({ authedPage: page }) => {
    await page.getByRole('button', { name: 'Sign Out' }).click();
    await page.waitForURL('/login');

    await page.goto('/');
    await page.waitForURL('/login');
  });

  // -----------------------------------------------------------------------
  // Permission-gated routes - Access Denied
  // -----------------------------------------------------------------------
  test('user role sees Access Denied on /users page', async ({ authedPage: page }) => {
    // User role does not have 'users:manage' permission.
    // The route exists in the layout but the ProtectedRoute renders AccessDenied.
    await page.goto('/users');
    await expect(page.getByText('Access Denied')).toBeVisible();
  });

  test('user role sees Access Denied on /schema page', async ({ authedPage: page }) => {
    // User role does not have 'bss:upload_schema' permission.
    await page.goto('/schema');
    await expect(page.getByText('Access Denied')).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Header branding link
  // -----------------------------------------------------------------------
  test('clicking header brand navigates to home', async ({ authedPage: page }) => {
    await page.locator('.app-sidebar').getByText('Generate').click();
    await page.waitForURL('/generate');

    await page.locator('.header-brand').click();
    await page.waitForURL('/');
  });
});
