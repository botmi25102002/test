import { test, expect } from '@playwright/test';

// Helper to generate a random email
const randomEmail = () => `user_${Math.random().toString(36).substring(7)}@test.com`;

test.describe('Todo App E2E', () => {
  test('Full User Journey', async ({ page }) => {
    const email = randomEmail();
    const password = 'Password@123';

    // 1. Register & Login
    await page.goto('/');
    
    // Switch to Register page
    await page.getByRole('link', { name: 'Sign up' }).click();
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByLabel('Confirm Password').fill(password);
    await page.getByRole('button', { name: 'Create Account' }).click();

    // Verify successful login (shows Todo dashboard)
    await expect(page.getByText('My Todos')).toBeVisible();

    // 2. Create a todo
    const todoTitle = `New Todo ${Date.now()}`;
    await page.getByRole('button', { name: 'Add Todo' }).click();
    await page.getByPlaceholder('What needs to be done?').fill(todoTitle);
    await page.getByRole('button', { name: 'Create', exact: true }).click();

    // Verify item is in UI
    await expect(page.getByText(todoTitle)).toBeVisible();

    // 3. Toggle completion
    const checkbox = page.getByRole('checkbox', { name: todoTitle });
    await expect(checkbox).not.toBeChecked();
    
    // Check it
    await checkbox.check();
    await expect(checkbox).toBeChecked();

    // Uncheck it (testing B5 fix)
    await checkbox.uncheck();
    await expect(checkbox).not.toBeChecked();

    // 4. Logout
    await page.getByRole('button', { name: 'Logout' }).click();
    
    // Verify back to login page
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
  });

  test('Cross-User Data Isolation', async ({ browser }) => {
    const userAEmail = randomEmail();
    const userBEmail = randomEmail();
    const password = 'Password@123';
    const secretTodo = `Top Secret Todo ${Date.now()}`;

    // User A Session
    const contextA = await browser.newContext();
    const pageA = await contextA.newPage();
    
    // Register User A
    await pageA.goto('/');
    await pageA.getByRole('link', { name: 'Sign up' }).click();
    await pageA.getByLabel('Email').fill(userAEmail);
    await pageA.getByLabel('Password', { exact: true }).fill(password);
    await pageA.getByLabel('Confirm Password').fill(password);
    await pageA.getByRole('button', { name: 'Create Account' }).click();

    // User A creates a private todo
    await expect(pageA.getByText('My Todos')).toBeVisible();
    await pageA.getByRole('button', { name: 'Add Todo' }).click();
    await pageA.getByPlaceholder('What needs to be done?').fill(secretTodo);
    await pageA.getByRole('button', { name: 'Create', exact: true }).click();
    await expect(pageA.getByText(secretTodo)).toBeVisible();

    // User B Session
    const contextB = await browser.newContext();
    const pageB = await contextB.newPage();
    
    // Register User B
    await pageB.goto('/');
    await pageB.getByRole('link', { name: 'Sign up' }).click();
    await pageB.getByLabel('Email').fill(userBEmail);
    await pageB.getByLabel('Password', { exact: true }).fill(password);
    await pageB.getByLabel('Confirm Password').fill(password);
    await pageB.getByRole('button', { name: 'Create Account' }).click();

    // User B confirms the item is NOT visible
    await expect(pageB.getByText('My Todos')).toBeVisible();
    await pageB.waitForTimeout(1000); // Wait for potential data load
    await expect(pageB.getByText(secretTodo)).not.toBeVisible();
    
    await contextA.close();
    await contextB.close();
  });
});
