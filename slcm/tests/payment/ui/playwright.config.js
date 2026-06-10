// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
	testDir: __dirname,
	timeout: 60_000,
	retries: 0,
	use: {
		baseURL: process.env.PAYMENT_UI_BASE_URL || 'http://127.0.0.1:8001',
		headless: process.env.PAYMENT_UI_HEADED !== '1',
		screenshot: 'only-on-failure',
		trace: 'retain-on-failure',
	},
	reporter: [['list']],
});
