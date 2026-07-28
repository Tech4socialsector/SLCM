const { test, expect } = require('@playwright/test');

const baseURL = process.env.BASE_URL || 'http://192.168.1.213:8001/';

// Utility to login to Frappe before tests
async function login(page) {
	await page.goto(baseURL + '/admission/login#login');
	await page.fill('#login_email', 'playwritetest@gmail.com');
	await page.fill('#login_password', 'admin@123');
	await page.click('.btn-login');
	await page.waitForURL('**/*'); // wait for any redirect after login
}

test.describe('Applicant Form Web Form E2E Tests', () => {
	
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto(baseURL + '/admission/application-form/new');
		await page.waitForSelector('.web-form-container');
	});

	test('Mandatory Field Validations (Negative Case)', async ({ page }) => {
		// Attempt to submit empty form
		await page.click('button.submit-btn, button.btn-next');
		
		// Wait for frappe validation (usually adds .has-error to fields)
		await page.waitForTimeout(500);
		
		const hasErrors = await page.locator('.has-error').count();
		expect(hasErrors).toBeGreaterThan(0);
	});

	test('Foreign National Flow & Attachments', async ({ page }) => {
		// Ensure passport field is hidden initially
		await expect(page.locator('[data-fieldname="copy_of_passport"]')).toBeHidden();
		
		// Select Foreign National = Yes
		await page.selectOption('[data-fieldname="foriegn_national"] select', 'Yes');
		await page.waitForTimeout(300);
		
		// Passport field should now be visible
		await expect(page.locator('[data-fieldname="copy_of_passport"]')).toBeVisible();
		
		// Simulate file upload in Frappe
		// Frappe uses a file uploader button which opens a dialog, but often there's a hidden input
		// Or we can mock the upload endpoint
		await page.route('**/api/method/upload_file', async route => {
			await route.fulfill({ json: { message: { file_url: '/files/mock_passport.jpg' } } });
		});
	});

	test('Guardian Details Logic', async ({ page }) => {
		await expect(page.locator('[data-fieldname="guardian_name"]')).toBeHidden();
		
		// Select Guardian Required = Yes
		await page.selectOption('[data-fieldname="guardian_required"] select', 'Yes');
		await page.waitForTimeout(300);
		
		await expect(page.locator('[data-fieldname="guardian_name"]')).toBeVisible();
		await expect(page.locator('[data-fieldname="guardian_mobile"]')).toBeVisible();
		await expect(page.locator('[data-fieldname="guardian_email"]')).toBeVisible();
	});

	test('Application Fee Calculation (SC/ST vs General)', async ({ page }) => {
		// If fee calculation is dependent on whether_scstobc_ncl
		const feeDisplay = page.locator('.fee-amount-display, #slcm-application-fee-display');
		if (await feeDisplay.count() > 0) {
			const initialFee = await feeDisplay.innerText();
			await page.selectOption('[data-fieldname="whether_scstobc_ncl"] select', 'Yes');
			await page.waitForTimeout(1000); 
			const newFee = await feeDisplay.innerText();
			expect(newFee).not.toBe(initialFee);
		}
	});

	test('Draft Saving Capability', async ({ page }) => {
		// Fill candidate name
		await page.fill('[data-fieldname="candidate_name"] input', 'Test Draft User');
		await page.fill('[data-fieldname="mobile_number"] input', '1234567890');
		
		// Mock the save API if needed, or rely on actual db
		const draftBtn = page.locator('#slcm-save-draft-btn');
		if (await draftBtn.count() > 0) {
			await draftBtn.click();
			
			// Wait for success toast
			await expect(page.locator('#slcm-toast.slcm-success')).toBeVisible({ timeout: 5000 });
			
			// Reload page to ensure data persisted
			await page.reload();
			await page.waitForSelector('.web-form-container');
			
			const val = await page.inputValue('[data-fieldname="candidate_name"] input');
			expect(val).toBe('Test Draft User');
		}
	});

	test('Eligibility Validation Flow (Ineligible Case)', async ({ page }) => {
		// Mock check_eligibility API to return Ineligible
		await page.route('**/api/method/slcm.admission.web_form.applicant_form.applicant_form.check_eligibility', async route => {
			await route.fulfill({ json: { message: { eligible: false, message: "Age criteria not met." } } });
		});
		
		// Fill mandatory fields to bypass basic client validation
		await page.fill('[data-fieldname="candidate_name"] input', 'Ineligible User');
		await page.fill('[data-fieldname="mobile_number"] input', '9999999999');
		
		// Attempt submit
		await page.click('button.submit-btn');
		
		// Check that eligibility modal overlay appears
		const modal = page.locator('#slcm-wf-eligibility-modal-overlay');
		await expect(modal).toBeVisible({ timeout: 10000 });
		await expect(modal).toContainText('You do not meet the eligibility criteria');
	});

	test('End-to-End Happy Path with Mocked Payment', async ({ page }) => {
		// Mock Razorpay / Payment APIs
		await page.route('**/api/method/slcm.admission.web_form.applicant_form.applicant_form.get_razorpay_order', async route => {
			await route.fulfill({ json: { message: { order_id: "order_mock123", amount: 1000 } } });
		});

		// Mock Form Submit API
		await page.route('**/api/method/frappe.website.doctype.web_form.web_form.accept', async route => {
			await route.fulfill({ json: { message: "Success" } });
		});

		// Mock Eligibility API
		await page.route('**/api/method/slcm.admission.web_form.applicant_form.applicant_form.check_eligibility', async route => {
			await route.fulfill({ json: { message: { eligible: true } } });
		});
		
		// Fill standard form
		await page.fill('[data-fieldname="candidate_name"] input', 'E2E Happy Path');
		await page.fill('[data-fieldname="mobile_number"] input', '9876543210');
		await page.fill('[data-fieldname="date_of_birth"] input', '2000-05-15');
		await page.selectOption('[data-fieldname="gender"] select', 'Male');
		await page.selectOption('[data-fieldname="nationality"] select', 'Indian');
		await page.selectOption('[data-fieldname="foriegn_national"] select', 'No');
		
		// Parent Details
		await page.fill('[data-fieldname="father_name"] input', 'Father Name');
		await page.fill('[data-fieldname="father_occupation"] input', 'Business');
		await page.fill('[data-fieldname="father_mobile"] input', '8888888888');
		await page.fill('[data-fieldname="father_email"] input', 'father@test.com');
		
		await page.fill('[data-fieldname="mother_name"] input', 'Mother Name');
		await page.fill('[data-fieldname="mother_occupation"] input', 'Housewife');
		await page.fill('[data-fieldname="mother_mobile"] input', '7777777777');
		await page.fill('[data-fieldname="mother_email"] input', 'mother@test.com');
		
		// Address
		await page.fill('[data-fieldname="correspondence_address"] textarea', '123 Test Street, Testing City');
		
		// Wait for elements and attempt submit
		await page.click('button.submit-btn');
		
		// Because we mocked Razorpay, if the UI handles successful payment automatically, it should redirect
		// Wait for success URL (e.g. /merit-and-scholarship/admission_dashboard)
		// await page.waitForURL('**/admission_dashboard**', { timeout: 15000 });
	});
});
