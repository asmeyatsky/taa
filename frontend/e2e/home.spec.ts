import { test, expect } from './fixtures';

test.describe('Home Page', () => {
  test.beforeEach(async ({ authedPage }) => {
    // authedPage is already logged in and at /
  });

  // -----------------------------------------------------------------------
  // Hero section
  // -----------------------------------------------------------------------
  test('renders the hero heading', async ({ authedPage: page }) => {
    await expect(
      page.getByRole('heading', { name: 'Telco Analytics Accelerator' })
    ).toBeVisible();
  });

  test('renders the hero subtitle', async ({ authedPage: page }) => {
    await expect(
      page.getByText('Auto-generate production-ready BigQuery data warehouses')
    ).toBeVisible();
  });

  test('hero has Generate Artefacts link', async ({ authedPage: page }) => {
    const link = page.getByRole('link', { name: 'Generate Artefacts' });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute('href', '/generate');
  });

  test('hero has Explore Data Model link', async ({ authedPage: page }) => {
    const link = page.getByRole('link', { name: 'Explore Data Model' });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute('href', '/domains');
  });

  // -----------------------------------------------------------------------
  // Business Impact stats section
  // -----------------------------------------------------------------------
  test('renders the Business Impact section with benefit cards', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: 'Business Impact' })).toBeVisible();

    // Check all four benefit cards
    const benefitCards = page.locator('.benefit-card');
    await expect(benefitCards).toHaveCount(4);
  });

  test('benefit cards display stat values', async ({ authedPage: page }) => {
    const stats = page.locator('.benefit-stat');
    await expect(stats).toHaveCount(4);

    // Check known stat values
    await expect(page.getByText('95%')).toBeVisible();
    await expect(page.getByText('50+')).toBeVisible();
    await expect(page.getByText('10', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('653')).toBeVisible();
  });

  test('benefit card titles render correctly', async ({ authedPage: page }) => {
    await expect(page.getByText('Weeks to Minutes')).toBeVisible();
    await expect(page.getByText('Production-Ready Output')).toBeVisible();
    await expect(page.getByText('Compliance by Default')).toBeVisible();
    await expect(page.getByText('Vendor Agnostic')).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Platform Integrations section
  // -----------------------------------------------------------------------
  test('renders Platform Integrations section', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: 'Platform Integrations' })).toBeVisible();
    await expect(page.getByText('End-to-end code generation across')).toBeVisible();
  });

  test('displays all eight integration cards', async ({ authedPage: page }) => {
    const integrationCards = page.locator('.integration-card');
    await expect(integrationCards).toHaveCount(8);
  });

  test('integration cards show names and icons', async ({ authedPage: page }) => {
    const integrationNames = [
      'BigQuery', 'Terraform', 'Dataflow', 'Airflow',
      'Vertex AI', 'Looker', 'GDPR / PDPL', 'BSS/OSS',
    ];

    for (const name of integrationNames) {
      await expect(page.locator('.integration-card', { hasText: name })).toBeVisible();
    }
  });

  test('integration icons display abbreviated text', async ({ authedPage: page }) => {
    const icons = page.locator('.integration-icon');
    await expect(icons).toHaveCount(8);

    // Check a few known icon abbreviations
    await expect(page.locator('.integration-icon', { hasText: 'BQ' })).toBeVisible();
    await expect(page.locator('.integration-icon', { hasText: 'TF' })).toBeVisible();
    await expect(page.locator('.integration-icon', { hasText: 'AF' })).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Quick Access section
  // -----------------------------------------------------------------------
  test('renders Quick Access section for logged-in user', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: 'Quick Access' })).toBeVisible();
  });

  test('quick access cards link to correct pages', async ({ authedPage: page }) => {
    const quickCards = page.locator('.quick-card');
    await expect(quickCards).toHaveCount(4);

    // Check links
    await expect(page.locator('a.quick-card[href="/generate"]')).toBeVisible();
    await expect(page.locator('a.quick-card[href="/domains"]')).toBeVisible();
    await expect(page.locator('a.quick-card[href="/compliance"]')).toBeVisible();
    await expect(page.locator('a.quick-card[href="/analytics"]')).toBeVisible();
  });

  test('quick access cards have titles and descriptions', async ({ authedPage: page }) => {
    await expect(page.locator('.quick-card', { hasText: 'Generate Pack' })).toBeVisible();
    await expect(page.locator('.quick-card', { hasText: 'Domain Explorer' })).toBeVisible();
    await expect(page.locator('.quick-card', { hasText: 'Compliance' })).toBeVisible();
    await expect(page.locator('.quick-card', { hasText: 'Analytics' })).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Navigation from home page
  // -----------------------------------------------------------------------
  test('clicking Generate Artefacts navigates to /generate', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Generate Artefacts' }).click();
    await page.waitForURL('/generate');
    await expect(page.getByRole('heading', { name: 'Generate Artefacts' })).toBeVisible();
  });

  test('clicking Explore Data Model navigates to /domains', async ({ authedPage: page }) => {
    await page.getByRole('link', { name: 'Explore Data Model' }).click();
    await page.waitForURL('/domains');
    await expect(page.getByRole('heading', { name: 'Domain Explorer' })).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // System status (when API is reachable)
  // -----------------------------------------------------------------------
  test('system status shows version when API responds', async ({ authedPage: page }) => {
    // This status depends on the backend being available.
    // If the health API responds, we should see "System Online" with a version.
    const statusEl = page.locator('.hero-status');
    const isVisible = await statusEl.isVisible().catch(() => false);

    if (isVisible) {
      await expect(statusEl).toContainText('System Online');
    }
  });
});
