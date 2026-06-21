// /**
//  * Global defaults for frappe.ui.FileUploader (desk + website Web Forms).
//  * Merged into options passed to the real FileUploader; callers can override any key.
//  *
//  * Frappe file_uploader.bundle.js + FileUploader.vue / FilePreview.vue:
//  * - Link / Library / Camera / Drive: allow_web_link, disable_file_browser, allow_take_photo, allow_google_drive
//  * - Optimize / Private UI + "Set all private": allow_toggle_optimize, allow_toggle_private
//  * - Public default: make_attachments_public (FileUploader.vue: private = !make_attachments_public || !can_upload_public_files)
//  */
// (function () {
// 	'use strict';

// 	var PATCHED = '_slcmFileUploaderDefaults';

// 	var DEFAULTS = {
// 		disable_file_browser: true,
// 		allow_web_link: false,
// 		allow_take_photo: false,
// 		allow_google_drive: false,
// 		allow_toggle_optimize: false,
// 		allow_toggle_private: true,
// 		make_attachments_public: 0,
// 	};

// 	function apply() {
// 		if (typeof frappe === 'undefined' || !frappe.ui) return;
// 		var Original = frappe.ui.FileUploader;
// 		if (!Original || Original[PATCHED]) return;

// 		var SLCM_PRIVATE_FORMS = { 'applicant-form': true, 'pace-application-form': true };

// 		function FileUploaderWithSlcmDefaults(opts) {
// 			// Apply SLCM defaults only on the specific web forms that require private-only uploads.
// 			var wf = typeof frappe !== 'undefined' && frappe.web_form;
// 			var formName = wf && (frappe.web_form.name || (frappe.web_form.web_form_doc && frappe.web_form.web_form_doc.name) || '');
// 			if (wf && SLCM_PRIVATE_FORMS[formName]) {
// 				var merged = Object.assign({}, DEFAULTS, opts || {});
// 				return new Original(merged);
// 			}
// 			return new Original(opts);
// 		}
// 		FileUploaderWithSlcmDefaults.UploadOptions = Original.UploadOptions;
// 		FileUploaderWithSlcmDefaults[PATCHED] = true;
// 		frappe.ui.FileUploader = FileUploaderWithSlcmDefaults;
// 	}

// 	function run() {
// 		if (typeof frappe === 'undefined' || typeof frappe.require !== 'function') return;
// 		frappe.require('file_uploader.bundle.js', apply);
// 	}

// 	// Safe boot: wait for frappe & frappe.require to be loaded (handles async/defer script loading in production)
// 	(function bootstrap() {
// 		var retryCount = 0;
// 		var timer = setInterval(function () {
// 			if (typeof frappe !== 'undefined' && typeof frappe.require === 'function') {
// 				clearInterval(timer);
// 				run();
// 				if (frappe.ready) {
// 					frappe.ready(run);
// 				}
// 			} else if (++retryCount > 100) {
// 				clearInterval(timer);
// 			}
// 		}, 100);
// 	})();
// })();
