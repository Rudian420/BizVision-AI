import { expect, test } from '@playwright/test';

test('landing page renders the BizVision hero', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/BizVision/i);
});
