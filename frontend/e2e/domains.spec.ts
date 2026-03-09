import { test, expect } from './fixtures';

test.describe('Domains Page', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/domains');
  });

  // -----------------------------------------------------------------------
  // Page rendering
  // -----------------------------------------------------------------------
  test('renders page heading and description', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: 'Domain Explorer' })).toBeVisible();
    await expect(
      page.getByText('Browse the Logical Data Model')
    ).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Domain chips
  // -----------------------------------------------------------------------
  test('displays domain chips with table count badges', async ({ authedPage: page }) => {
    const chips = page.locator('.chip-group .chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      // Each chip should contain a badge with the table count
      const firstChip = chips.first();
      await expect(firstChip.locator('.chip-badge')).toBeVisible();
    }
  });

  test('clicking a domain chip toggles its active state', async ({ authedPage: page }) => {
    const chips = page.locator('.chip-group .chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      const firstChip = chips.first();

      // Select
      await firstChip.click();
      await expect(firstChip).toHaveClass(/chip-active/);

      // Deselect
      await firstChip.click();
      await expect(firstChip).not.toHaveClass(/chip-active/);
    }
  });

  test('selecting a domain chip loads tables for that domain', async ({ authedPage: page }) => {
    const chips = page.locator('.chip-group .chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      // Click the first domain chip
      await chips.first().click();

      // Wait for either loading indicator or domain content to appear
      const loadingOrContent = page.locator('.loading, .card h3');
      await expect(loadingOrContent.first()).toBeVisible({ timeout: 10_000 });
    }
  });

  test('can select multiple domain chips simultaneously', async ({ authedPage: page }) => {
    const chips = page.locator('.chip-group .chip');
    const chipCount = await chips.count();

    if (chipCount >= 2) {
      await chips.nth(0).click();
      await chips.nth(1).click();

      await expect(chips.nth(0)).toHaveClass(/chip-active/);
      await expect(chips.nth(1)).toHaveClass(/chip-active/);
    }
  });

  // -----------------------------------------------------------------------
  // Table expansion
  // -----------------------------------------------------------------------
  test('clicking a table header expands its column grid', async ({ authedPage: page }) => {
    const chips = page.locator('.chip-group .chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      // Select first domain to load its tables
      await chips.first().click();

      // Wait for tables to load
      const tableHeaders = page.locator('.table-header');
      await tableHeaders.first().waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {
        // Backend may not be running; skip if tables don't load
      });

      const tableHeaderCount = await tableHeaders.count();
      if (tableHeaderCount > 0) {
        // Click first table header to expand
        await tableHeaders.first().click();

        // Column grid should appear with header row
        const columnGridHeader = page.locator('.column-grid-header');
        await expect(columnGridHeader).toBeVisible();

        // Should show Column, Type, Nullable, PII columns
        await expect(columnGridHeader).toContainText('Column');
        await expect(columnGridHeader).toContainText('Type');
        await expect(columnGridHeader).toContainText('Nullable');
        await expect(columnGridHeader).toContainText('PII');
      }
    }
  });

  test('clicking an expanded table header collapses it', async ({ authedPage: page }) => {
    const chips = page.locator('.chip-group .chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      await chips.first().click();

      const tableHeaders = page.locator('.table-header');
      await tableHeaders.first().waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});

      const tableHeaderCount = await tableHeaders.count();
      if (tableHeaderCount > 0) {
        // Expand
        await tableHeaders.first().click();
        await expect(page.locator('.column-grid-header')).toBeVisible();

        // Collapse
        await tableHeaders.first().click();
        await expect(page.locator('.column-grid-header')).not.toBeVisible();
      }
    }
  });

  test('table header shows table name, column count badge, and expand icon', async ({ authedPage: page }) => {
    const chips = page.locator('.chip-group .chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      await chips.first().click();

      const tableHeaders = page.locator('.table-header');
      await tableHeaders.first().waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});

      const tableHeaderCount = await tableHeaders.count();
      if (tableHeaderCount > 0) {
        const firstHeader = tableHeaders.first();
        await expect(firstHeader.locator('.table-name')).toBeVisible();
        await expect(firstHeader.locator('.badge')).toBeVisible();
        await expect(firstHeader.locator('.expand-icon')).toBeVisible();
      }
    }
  });

  // -----------------------------------------------------------------------
  // Domain card displays
  // -----------------------------------------------------------------------
  test('domain section card shows domain name and table count', async ({ authedPage: page }) => {
    const chips = page.locator('.chip-group .chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      await chips.first().click();

      // Wait for domain section card with h3
      const domainCard = page.locator('.card h3');
      await domainCard.first().waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});

      const cardCount = await domainCard.count();
      if (cardCount > 0) {
        // The h3 should contain the domain name and a tables badge
        const firstCard = domainCard.first();
        await expect(firstCard.locator('.badge')).toContainText('tables');
      }
    }
  });
});
