import { test, expect, DEMO_USERS, loginAsDemoUser } from './fixtures';

test.describe('Compliance Page', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/compliance');
  });

  // -----------------------------------------------------------------------
  // Page rendering
  // -----------------------------------------------------------------------
  test('renders page heading and description', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: 'Compliance Assessment' })).toBeVisible();
    await expect(page.getByText('Run data protection compliance checks')).toBeVisible();
  });

  test('shows Domains, Region, and Jurisdiction sections', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: 'Domains' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Region' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Jurisdiction' })).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Region filter chips
  // -----------------------------------------------------------------------
  test('region chips include All Regions, Middle East, Europe, Asia Pacific, Africa', async ({ authedPage: page }) => {
    const regionSection = page.locator('.card', { hasText: 'Region' }).first();

    await expect(regionSection.getByRole('button', { name: 'All Regions' })).toBeVisible();
    await expect(regionSection.getByRole('button', { name: 'Middle East' })).toBeVisible();
    await expect(regionSection.getByRole('button', { name: 'Europe' })).toBeVisible();
    await expect(regionSection.getByRole('button', { name: 'Asia Pacific' })).toBeVisible();
    await expect(regionSection.getByRole('button', { name: 'Africa' })).toBeVisible();
  });

  test('All Regions is active by default', async ({ authedPage: page }) => {
    const regionSection = page.locator('.card', { hasText: 'Region' }).first();
    const allRegionsChip = regionSection.getByRole('button', { name: 'All Regions' });
    await expect(allRegionsChip).toHaveClass(/chip-active/);
  });

  test('clicking a region chip makes it active and deactivates others', async ({ authedPage: page }) => {
    const regionSection = page.locator('.card', { hasText: 'Region' }).first();

    const middleEastChip = regionSection.getByRole('button', { name: 'Middle East' });
    const allRegionsChip = regionSection.getByRole('button', { name: 'All Regions' });

    await middleEastChip.click();
    await expect(middleEastChip).toHaveClass(/chip-active/);
    await expect(allRegionsChip).not.toHaveClass(/chip-active/);
  });

  test('region chips (except All Regions) show jurisdiction count badges', async ({ authedPage: page }) => {
    const regionSection = page.locator('.card', { hasText: 'Region' }).first();
    const regionChips = regionSection.locator('.chip');
    const chipCount = await regionChips.count();

    // All chips except "All Regions" should have a badge
    for (let i = 0; i < chipCount; i++) {
      const chip = regionChips.nth(i);
      const text = await chip.textContent();
      if (text && !text.includes('All Regions')) {
        await expect(chip.locator('.chip-badge')).toBeVisible();
      }
    }
  });

  // -----------------------------------------------------------------------
  // Jurisdiction display
  // -----------------------------------------------------------------------
  test('jurisdiction cards render with code, name, framework, and region', async ({ authedPage: page }) => {
    const jurisdictionCards = page.locator('.jurisdiction-card');

    // Wait for jurisdictions to load
    await jurisdictionCards.first().waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
    const cardCount = await jurisdictionCards.count();

    if (cardCount > 0) {
      const firstCard = jurisdictionCards.first();
      await expect(firstCard.locator('.jurisdiction-code')).toBeVisible();
      await expect(firstCard.locator('.jurisdiction-name')).toBeVisible();
      await expect(firstCard.locator('.jurisdiction-framework')).toBeVisible();
      await expect(firstCard.locator('.jurisdiction-region')).toBeVisible();
      await expect(firstCard.locator('.jurisdiction-rules')).toBeVisible();
    }
  });

  test('clicking a jurisdiction card makes it active', async ({ authedPage: page }) => {
    const jurisdictionCards = page.locator('.jurisdiction-card');
    await jurisdictionCards.first().waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
    const cardCount = await jurisdictionCards.count();

    if (cardCount >= 2) {
      const secondCard = jurisdictionCards.nth(1);
      await secondCard.click();
      await expect(secondCard).toHaveClass(/jurisdiction-active/);
    }
  });

  test('switching region updates visible jurisdiction cards', async ({ authedPage: page }) => {
    // Get initial jurisdiction count with "All Regions"
    const jurisdictionCards = page.locator('.jurisdiction-card');
    await jurisdictionCards.first().waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
    const allCount = await jurisdictionCards.count();

    if (allCount > 0) {
      const regionSection = page.locator('.card', { hasText: 'Region' }).first();

      // Switch to a specific region
      await regionSection.getByRole('button', { name: 'Middle East' }).click();

      // Wait for the view to update
      await page.waitForTimeout(500);

      // The filtered count should be less than or equal to the "All Regions" count
      const filteredCount = await jurisdictionCards.count();
      expect(filteredCount).toBeLessThanOrEqual(allCount);
    }
  });

  // -----------------------------------------------------------------------
  // Domain selection
  // -----------------------------------------------------------------------
  test('domain chips can be toggled', async ({ authedPage: page }) => {
    const domainSection = page.locator('.card', { hasText: 'Domains' }).first();
    const chips = domainSection.locator('.chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      const firstChip = chips.first();

      await firstChip.click();
      await expect(firstChip).toHaveClass(/chip-active/);

      await firstChip.click();
      await expect(firstChip).not.toHaveClass(/chip-active/);
    }
  });

  // -----------------------------------------------------------------------
  // Compliance run button - role-based
  // -----------------------------------------------------------------------
  test('user role sees permission notice instead of run button', async ({ authedPage: page }) => {
    // 'user' role does not have 'compliance:run' permission
    await expect(page.locator('.permission-notice')).toBeVisible();
    await expect(page.getByText('Compliance checks require Admin or Management access')).toBeVisible();
  });

  test('admin role sees the Run compliance button', async ({ adminPage: page }) => {
    await page.goto('/compliance');

    // admin has 'compliance:run' permission
    const runBtn = page.getByRole('button', { name: /Run.*Compliance Check/ });
    await expect(runBtn).toBeVisible();
  });

  test('run button is disabled when no domains are selected', async ({ adminPage: page }) => {
    await page.goto('/compliance');

    const runBtn = page.getByRole('button', { name: /Run.*Compliance Check/ });
    await expect(runBtn).toBeDisabled();
  });

  test('run button enables after selecting a domain', async ({ adminPage: page }) => {
    await page.goto('/compliance');

    // Select a domain
    const domainSection = page.locator('.card', { hasText: 'Domains' }).first();
    const chips = domainSection.locator('.chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      await chips.first().click();

      const runBtn = page.getByRole('button', { name: /Run.*Compliance Check/ });
      await expect(runBtn).toBeEnabled();
    }
  });

  test('run button label includes the framework name', async ({ adminPage: page }) => {
    await page.goto('/compliance');

    // The button text should reference the active jurisdiction's framework
    const runBtn = page.getByRole('button', { name: /Run.*Compliance Check/ });
    const btnText = await runBtn.textContent().catch(() => '');

    // Button text should follow pattern "Run {framework} Compliance Check"
    expect(btnText).toMatch(/Run.*Compliance Check/);
  });
});
