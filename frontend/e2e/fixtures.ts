import { test as base, type Page } from '@playwright/test';

// ---------------------------------------------------------------------------
// Demo-user credentials and metadata
// ---------------------------------------------------------------------------
export interface DemoUser {
  id: string;
  name: string;
  email: string;
  role: 'user' | 'admin' | 'management';
  username: string;
  password: string;
}

export const DEMO_USERS: Record<string, DemoUser> = {
  alex: {
    id: '1',
    name: 'Alex Analyst',
    email: 'alex@telco.com',
    role: 'user',
    username: 'alex',
    password: 'analyst123',
  },
  sarah: {
    id: '2',
    name: 'Sarah Admin',
    email: 'sarah@telco.com',
    role: 'admin',
    username: 'sarah',
    password: 'admin123',
  },
  mike: {
    id: '3',
    name: 'Mike Director',
    email: 'mike@telco.com',
    role: 'management',
    username: 'mike',
    password: 'director123',
  },
};

// ---------------------------------------------------------------------------
// Helper: perform a demo-user login via the Login page's demo-user buttons.
// This works regardless of whether the backend is running because the
// AuthContext falls back to demo mode when the API is unreachable.
// ---------------------------------------------------------------------------
export async function loginAsDemoUser(page: Page, user: DemoUser) {
  await page.goto('/login');

  // Make sure the demo-users tab is active (it is default, but be explicit)
  const demoTab = page.getByRole('button', { name: 'Demo Users' });
  await demoTab.click();

  // Click the matching demo-user button
  await page.getByRole('button', { name: user.name }).click();

  // After clicking, the app navigates to /. Wait for the layout to appear.
  await page.waitForURL('/');
}

// ---------------------------------------------------------------------------
// Extended test fixture that exposes a pre-authenticated page.
// Usage:  import { test } from './fixtures';
//         test('something', async ({ authedPage }) => { ... })
// ---------------------------------------------------------------------------
type Fixtures = {
  /** A page that is already logged in as Alex (user role). */
  authedPage: Page;
  /** A page that is already logged in as Sarah (admin role). */
  adminPage: Page;
};

export const test = base.extend<Fixtures>({
  authedPage: async ({ page }, use) => {
    await loginAsDemoUser(page, DEMO_USERS.alex);
    await use(page);
  },
  adminPage: async ({ browser }, use) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await loginAsDemoUser(page, DEMO_USERS.sarah);
    await use(page);
    await ctx.close();
  },
});

export { expect } from '@playwright/test';
