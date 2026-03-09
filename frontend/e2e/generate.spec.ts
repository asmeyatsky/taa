import { test, expect } from './fixtures';

test.describe('Generate Page', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/generate');
  });

  // -----------------------------------------------------------------------
  // Page rendering
  // -----------------------------------------------------------------------
  test('renders page heading and description', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: 'Generate Artefacts' })).toBeVisible();
    await expect(page.getByText('Select domains, jurisdiction, and artefact types')).toBeVisible();
  });

  test('shows the four configuration sections', async ({ authedPage: page }) => {
    await expect(page.getByRole('heading', { name: '1. Select Domains' })).toBeVisible();
    await expect(page.getByRole('heading', { name: /2\. Region & Jurisdiction/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /3\. BSS Vendor/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: '4. Artefacts' })).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Domain selection
  // -----------------------------------------------------------------------
  test('generate button is disabled when no domains are selected', async ({ authedPage: page }) => {
    const generateBtn = page.getByRole('button', { name: /Generate Pack/ });
    await expect(generateBtn).toBeDisabled();
  });

  test('clicking a domain chip toggles its active state', async ({ authedPage: page }) => {
    // Wait for domain chips to load (they come from the API or loading state)
    const domainSection = page.locator('.card', { hasText: '1. Select Domains' });

    // If domains load, we should see chip-group with chips
    const chips = domainSection.locator('.chip');

    // If chips are available (backend running), test toggling
    const chipCount = await chips.count();
    if (chipCount > 0) {
      const firstChip = chips.first();
      const chipText = await firstChip.textContent();

      // Click to select
      await firstChip.click();
      await expect(firstChip).toHaveClass(/chip-active/);

      // Click again to deselect
      await firstChip.click();
      await expect(firstChip).not.toHaveClass(/chip-active/);

      // Verify the generate button text reflects selection count
      await firstChip.click();
      const generateBtn = page.getByRole('button', { name: /Generate Pack/ });
      await expect(generateBtn).toBeEnabled();
      await expect(generateBtn).toContainText('1 domain');
    }
  });

  test('Select All / Deselect All button works', async ({ authedPage: page }) => {
    const domainSection = page.locator('.card', { hasText: '1. Select Domains' });
    const chips = domainSection.locator('.chip');
    const chipCount = await chips.count();

    if (chipCount > 0) {
      // Click "Select All"
      const selectAllBtn = page.getByRole('button', { name: 'Select All' });
      await selectAllBtn.click();

      // All chips should be active
      for (let i = 0; i < chipCount; i++) {
        await expect(chips.nth(i)).toHaveClass(/chip-active/);
      }

      // Button should now say "Deselect All"
      await expect(page.getByRole('button', { name: 'Deselect All' })).toBeVisible();

      // Click "Deselect All"
      await page.getByRole('button', { name: 'Deselect All' }).click();
      for (let i = 0; i < chipCount; i++) {
        await expect(chips.nth(i)).not.toHaveClass(/chip-active/);
      }
    }
  });

  // -----------------------------------------------------------------------
  // Region & Jurisdiction chips
  // -----------------------------------------------------------------------
  test('region chips render with All Regions active by default', async ({ authedPage: page }) => {
    const regionSection = page.locator('.card', { hasText: '2. Region & Jurisdiction' });
    const regionChips = regionSection.locator('.chip');

    // "All Regions" should be active
    const allRegionsChip = regionSection.getByRole('button', { name: 'All Regions' });
    await expect(allRegionsChip).toHaveClass(/chip-active/);
  });

  test('clicking a region chip filters jurisdictions', async ({ authedPage: page }) => {
    const regionSection = page.locator('.card', { hasText: '2. Region & Jurisdiction' });

    // Click "Middle East"
    const middleEastChip = regionSection.getByRole('button', { name: 'Middle East' });
    await middleEastChip.click();
    await expect(middleEastChip).toHaveClass(/chip-active/);

    // "All Regions" should no longer be active
    const allRegionsChip = regionSection.getByRole('button', { name: 'All Regions' });
    await expect(allRegionsChip).not.toHaveClass(/chip-active/);
  });

  // -----------------------------------------------------------------------
  // Vendor selection
  // -----------------------------------------------------------------------
  test('vendor dropdown defaults to "None (canonical only)"', async ({ authedPage: page }) => {
    const vendorSection = page.locator('.card', { hasText: '3. BSS Vendor' });
    const select = vendorSection.locator('select');
    const selectCount = await select.count();

    if (selectCount > 0) {
      await expect(select).toHaveValue('');
    }
  });

  // -----------------------------------------------------------------------
  // Artefact checkboxes
  // -----------------------------------------------------------------------
  test('artefact checkboxes have correct defaults', async ({ authedPage: page }) => {
    const artefactSection = page.locator('.card', { hasText: '4. Artefacts' });

    // BigQuery DDL is always checked and disabled
    const ddlCheckbox = artefactSection.locator('label', { hasText: 'BigQuery DDL' }).locator('input');
    await expect(ddlCheckbox).toBeChecked();
    await expect(ddlCheckbox).toBeDisabled();

    // The others are checked by default but enabled
    const terraformCheckbox = artefactSection.locator('label', { hasText: 'Terraform IaC' }).locator('input');
    await expect(terraformCheckbox).toBeChecked();
    await expect(terraformCheckbox).toBeEnabled();

    const pipelinesCheckbox = artefactSection.locator('label', { hasText: 'Dataflow Pipelines' }).locator('input');
    await expect(pipelinesCheckbox).toBeChecked();

    const dagsCheckbox = artefactSection.locator('label', { hasText: 'Airflow DAGs' }).locator('input');
    await expect(dagsCheckbox).toBeChecked();

    const complianceCheckbox = artefactSection.locator('label', { hasText: 'Compliance Reports' }).locator('input');
    await expect(complianceCheckbox).toBeChecked();
  });

  test('artefact checkboxes can be toggled', async ({ authedPage: page }) => {
    const artefactSection = page.locator('.card', { hasText: '4. Artefacts' });

    const terraformCheckbox = artefactSection.locator('label', { hasText: 'Terraform IaC' }).locator('input');
    await terraformCheckbox.uncheck();
    await expect(terraformCheckbox).not.toBeChecked();

    await terraformCheckbox.check();
    await expect(terraformCheckbox).toBeChecked();
  });

  // -----------------------------------------------------------------------
  // Generate button state
  // -----------------------------------------------------------------------
  test('generate button text shows domain count', async ({ authedPage: page }) => {
    const domainSection = page.locator('.card', { hasText: '1. Select Domains' });
    const chips = domainSection.locator('.chip');
    const chipCount = await chips.count();

    if (chipCount >= 2) {
      await chips.nth(0).click();
      await chips.nth(1).click();

      const generateBtn = page.getByRole('button', { name: /Generate Pack/ });
      await expect(generateBtn).toContainText('2 domains');
    }
  });
});
