// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.pages["transcript-template-page"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Transcript Templates"),
		single_column: true,
	});

	// ── Constants ──────────────────────────────────────────────────────────────
	const API = {
		get_templates:        "slcm.slcm.page.transcript_template_page.transcript_template_page.get_templates",
		get_template:         "slcm.slcm.page.transcript_template_page.transcript_template_page.get_template",
		save_template:        "slcm.slcm.page.transcript_template_page.transcript_template_page.save_template",
		delete_template:      "slcm.slcm.page.transcript_template_page.transcript_template_page.delete_template",
		set_default:          "slcm.slcm.page.transcript_template_page.transcript_template_page.set_default",
		seed_default_templates: "slcm.slcm.page.transcript_template_page.transcript_template_page.seed_default_templates",
	};

	// ── State ──────────────────────────────────────────────────────────────────
	const state = {
		view:      "list",   // "list" | "configure"
		templates: [],
		current:   null,     // template being edited
		search:    "",
	};

	// ── Page skeleton ──────────────────────────────────────────────────────────
	$(wrapper).find(".page-content").html(`
		<div id="ttp-root" style="padding:16px;">

			<!-- ── LIST VIEW ──────────────────────────────────────── -->
			<div id="ttp-list-view">
				<!-- Toolbar -->
				<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:20px;">
					<div style="position:relative;flex:1;min-width:220px;max-width:400px;">
						<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
							fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
							style="position:absolute;left:10px;top:50%;transform:translateY(-50%);">
							<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
						</svg>
						<input id="ttp-search" type="text" placeholder="${__('Search templates…')}"
							style="width:100%;padding:7px 10px 7px 32px;border:1px solid #d1d8dd;border-radius:5px;
							       font-size:13px;outline:none;box-sizing:border-box;"/>
					</div>
					<div style="margin-left:auto;display:flex;gap:8px;align-items:center;">
						<button id="ttp-back-btn" class="btn btn-default btn-sm"
							style="display:flex;align-items:center;gap:5px;border-color:#c84630;color:#c84630;">
							<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
								fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
								<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
							</svg>
							${__("Back to Students")}
						</button>
						<button id="ttp-add-btn" class="btn btn-sm"
							style="background:#c84630;color:white;border:none;display:flex;align-items:center;gap:5px;">
							<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
								fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
								<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
							</svg>
							${__("Add Template")}
						</button>
					</div>
				</div>

				<!-- Template cards grid -->
				<div id="ttp-cards-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:20px;">
					<div style="text-align:center;padding:60px;color:#aaa;grid-column:1/-1;">
						<div class="ttp-spinner" style="margin:0 auto 10px;"></div>
						${__("Loading templates…")}
					</div>
				</div>
			</div>

			<!-- ── CONFIGURE VIEW ─────────────────────────────────── -->
			<div id="ttp-configure-view" style="display:none;">
				<!-- Header -->
				<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid #f0f0f0;">
					<button id="ttp-cfg-back" class="btn btn-xs btn-default"
						style="border-color:#c84630;color:#c84630;display:flex;align-items:center;gap:4px;">
						<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
						</svg>
						${__("Back")}
					</button>
					<div>
						<div style="font-size:18px;font-weight:700;color:#222;" id="ttp-cfg-title">${__("Configure Template")}</div>
						<div style="font-size:12px;color:#888;margin-top:2px;">${__("Configure the settings as per your need")}</div>
					</div>
					<div style="margin-left:auto;display:flex;gap:8px;">
						<button id="ttp-cfg-set-default" class="btn btn-sm btn-default"
							style="border-color:#6c757d;color:#6c757d;">
							${__("Set as Default")}
						</button>
						<button id="ttp-cfg-save" class="btn btn-sm"
							style="background:#c84630;color:white;border:none;min-width:80px;">
							${__("Save")}
						</button>
					</div>
				</div>

				<!-- Two-column layout: form left, preview right -->
				<div style="display:flex;gap:20px;align-items:flex-start;">

					<!-- Left: Accordion form -->
					<div id="ttp-cfg-form" style="flex:0 0 440px;min-width:300px;">

						<!-- Template Name & Type (always visible) -->
						<div style="background:#fff;border:1px solid #e4e7ea;border-radius:8px;padding:16px;margin-bottom:12px;">
							<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
								<div>
									<label class="ttp-label">${__("Template Name")} <span style="color:#c84630;">*</span></label>
									<input id="cfg-template_name" type="text" class="ttp-input"
										placeholder="${__('e.g. BA-LLB Template')}" />
								</div>
								<div>
									<label class="ttp-label">${__("Type")}</label>
									<select id="cfg-template_type" class="ttp-input">
										<option value="Custom">Custom</option>
										<option value="System">System</option>
									</select>
								</div>
								<div>
									<label class="ttp-label">${__("Page Size")}</label>
									<select id="cfg-page_size" class="ttp-input">
										<option value="A4">A4</option>
										<option value="Letter">Letter</option>
										<option value="A3">A3</option>
									</select>
								</div>
								<div>
									<label class="ttp-label">${__("Orientation")}</label>
									<select id="cfg-orientation" class="ttp-input">
										<option value="Portrait">Portrait</option>
										<option value="Landscape">Landscape</option>
									</select>
								</div>
							</div>
						</div>

						<!-- Accordion sections -->
						${accordion_section("institute_logo", "Institute Logo", `
							<div class="ttp-field-row">
								<div class="ttp-field">
									<label class="ttp-label">${__("Logo Image")}</label>
									<div id="cfg-institute_logo-wrap" class="ttp-attach-wrap">
										<img id="cfg-institute_logo-preview" src="" style="display:none;max-height:60px;max-width:160px;border-radius:4px;margin-bottom:6px;"/>
										<div id="cfg-institute_logo-placeholder" class="ttp-attach-placeholder">
											<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
											<span style="font-size:11px;color:#aaa;margin-top:4px;">${__("Click to upload")}</span>
										</div>
										<input id="cfg-institute_logo" type="file" accept="image/*" style="display:none;"/>
									</div>
									<div style="margin-top:6px;display:flex;gap:8px;align-items:center;">
										<button class="ttp-attach-btn" onclick="$(wrapper).find('#cfg-institute_logo').click();">${__("Upload")}</button>
										<button class="ttp-clear-btn" id="cfg-institute_logo-clear">${__("Clear")}</button>
									</div>
								</div>
								<div class="ttp-field">
									<label class="ttp-label">${__("Show Logo")}</label>
									<label class="ttp-toggle"><input type="checkbox" id="cfg-show_institute_logo" checked/><span class="ttp-slider"></span></label>
									<label class="ttp-label" style="margin-top:10px;">${__("Alignment")}</label>
									<select id="cfg-logo_alignment" class="ttp-input">
										<option value="Left">Left</option>
										<option value="Center" selected>Center</option>
										<option value="Right">Right</option>
									</select>
									<label class="ttp-label" style="margin-top:10px;">${__("Width (px)")}</label>
									<input id="cfg-logo_width" type="number" min="40" max="400" value="120" class="ttp-input"/>
								</div>
							</div>
						`)}

						${accordion_section("institute_address", "Institute Address", `
							<div class="ttp-field-row">
								<div class="ttp-field" style="flex:1;">
									<label class="ttp-label">${__("Institute Name")}</label>
									<input id="cfg-institute_name" type="text" class="ttp-input" placeholder="${__('Full institute name')}"/>
									<label class="ttp-label" style="margin-top:10px;">${__("Address")}</label>
									<textarea id="cfg-institute_address" class="ttp-input" rows="3" placeholder="${__('Street, Area')}"></textarea>
								</div>
								<div class="ttp-field" style="flex:1;">
									<label class="ttp-label">${__("City / State")}</label>
									<input id="cfg-institute_city" type="text" class="ttp-input"/>
									<label class="ttp-label" style="margin-top:10px;">${__("Country")}</label>
									<input id="cfg-institute_country" type="text" class="ttp-input"/>
									<label class="ttp-label" style="margin-top:10px;">${__("Show on Transcript")}</label>
									<label class="ttp-toggle"><input type="checkbox" id="cfg-show_institute_address" checked/><span class="ttp-slider"></span></label>
								</div>
							</div>
						`)}

						${accordion_section("basic_details", "Basic Details", `
							<div>
								<label class="ttp-label">${__("Transcript Header Title")}</label>
								<input id="cfg-header_title" type="text" class="ttp-input"
									placeholder="${__('e.g. OFFICIAL TRANSCRIPT OF ACADEMIC RECORDS')}"/>
							</div>
							<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px;">
								<label class="ttp-check-row"><input type="checkbox" id="cfg-show_student_photo" checked/> ${__("Show Student Photo")}</label>
								<label class="ttp-check-row"><input type="checkbox" id="cfg-show_registration_id" checked/> ${__("Show Registration ID")}</label>
								<label class="ttp-check-row"><input type="checkbox" id="cfg-show_cgpa" checked/> ${__("Show CGPA")}</label>
								<label class="ttp-check-row"><input type="checkbox" id="cfg-show_credits" checked/> ${__("Show Credits")}</label>
								<label class="ttp-check-row"><input type="checkbox" id="cfg-show_semester_wise" checked/> ${__("Semester-wise Grades")}</label>
							</div>
						`)}

						${accordion_section("signature_settings", "Signature Settings", `
							${signature_row(1)}
							<div style="margin-top:10px;"></div>
							${signature_row(2)}
							<div style="margin-top:10px;"></div>
							${signature_row(3)}
						`)}

						${accordion_section("watermark_logo", "Watermark Logo", `
							<div class="ttp-field-row">
								<div class="ttp-field">
									<label class="ttp-label">${__("Watermark Image")}</label>
									<div id="cfg-watermark_logo-wrap" class="ttp-attach-wrap">
										<img id="cfg-watermark_logo-preview" src="" style="display:none;max-height:60px;max-width:120px;border-radius:4px;margin-bottom:6px;"/>
										<div id="cfg-watermark_logo-placeholder" class="ttp-attach-placeholder">
											<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ccc" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
											<span style="font-size:11px;color:#aaa;margin-top:4px;">${__("Click to upload")}</span>
										</div>
										<input id="cfg-watermark_logo" type="file" accept="image/*" style="display:none;"/>
									</div>
									<div style="margin-top:6px;display:flex;gap:8px;">
										<button class="ttp-attach-btn" onclick="$(wrapper).find('#cfg-watermark_logo').click();">${__("Upload")}</button>
										<button class="ttp-clear-btn" id="cfg-watermark_logo-clear">${__("Clear")}</button>
									</div>
								</div>
								<div class="ttp-field">
									<label class="ttp-label">${__("Show Watermark")}</label>
									<label class="ttp-toggle"><input type="checkbox" id="cfg-show_watermark"/><span class="ttp-slider"></span></label>
									<label class="ttp-label" style="margin-top:10px;">${__("Watermark Text")}</label>
									<input id="cfg-watermark_text" type="text" class="ttp-input" placeholder="${__('e.g. CONFIDENTIAL')}"/>
									<label class="ttp-label" style="margin-top:10px;">${__("Opacity (%)")}</label>
									<input id="cfg-watermark_opacity" type="range" min="5" max="60" value="15"
										style="width:100%;accent-color:#c84630;"/>
									<span id="cfg-watermark_opacity-val" style="font-size:11px;color:#888;">15%</span>
								</div>
							</div>
						`)}
					</div>

					<!-- Right: Live preview -->
					<div style="flex:1;position:sticky;top:80px;">
						<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
							<span style="font-size:12px;font-weight:600;color:#555;">${__("Preview")}</span>
							<button id="ttp-refresh-preview" class="btn btn-xs btn-default"
								style="font-size:11px;display:flex;align-items:center;gap:4px;">
								<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"
									fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
									<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
								</svg>
								${__("Refresh")}
							</button>
						</div>
						<div id="ttp-preview-wrap" style="border:1px solid #e4e7ea;border-radius:6px;overflow:hidden;
							background:#f9fafb;display:flex;align-items:center;justify-content:center;min-height:500px;">
							<div id="ttp-preview-content" style="width:100%;padding:12px;box-sizing:border-box;">
								<!-- Rendered by render_preview() -->
							</div>
						</div>
						<div style="font-size:11px;color:#aaa;margin-top:6px;text-align:center;">
							${__("Preview is approximate — actual PDF may differ slightly.")}
						</div>
					</div>
				</div>
			</div>
		</div>

		<style>
		/* ── Spinner ────────────────────────────────── */
		.ttp-spinner {
			width:28px;height:28px;border:3px solid #e4e7ea;
			border-top-color:#c84630;border-radius:50%;
			animation:ttp-spin .8s linear infinite;
		}
		@keyframes ttp-spin { to { transform:rotate(360deg); } }

		/* ── Template card ──────────────────────────── */
		.ttp-card {
			background:#fff;border:1px solid #e4e7ea;border-radius:10px;
			overflow:hidden;cursor:pointer;
			transition:box-shadow .18s,transform .18s;
			display:flex;flex-direction:column;
		}
		.ttp-card:hover { box-shadow:0 4px 18px rgba(0,0,0,.12);transform:translateY(-2px); }
		.ttp-card-thumb {
			background:#f4f6f8;height:160px;
			display:flex;align-items:center;justify-content:center;
			border-bottom:1px solid #f0f0f0;overflow:hidden;position:relative;
		}
		.ttp-card-body { padding:14px 16px; }
		.ttp-card-title { font-size:14px;font-weight:700;color:#222;margin-bottom:2px; }
		.ttp-card-meta  { font-size:11px;color:#888; }
		.ttp-badge {
			display:inline-block;padding:1px 7px;border-radius:8px;font-size:10px;font-weight:600;
		}
		.ttp-badge-system  { background:#e8f0fe;color:#1a73e8; }
		.ttp-badge-custom  { background:#fce8e6;color:#c84630; }
		.ttp-badge-default { background:#e6f4ea;color:#1e7e34;margin-left:4px; }
		.ttp-card-actions {
			display:none;position:absolute;top:8px;right:8px;gap:4px;
		}
		.ttp-card-thumb:hover .ttp-card-actions { display:flex; }
		.ttp-action-btn {
			background:rgba(255,255,255,.9);border:1px solid #ddd;border-radius:4px;
			padding:3px 7px;font-size:11px;cursor:pointer;color:#555;
		}
		.ttp-action-btn:hover { background:#fff;color:#c84630;border-color:#c84630; }
		.ttp-action-btn.danger:hover { color:#dc3545;border-color:#dc3545; }

		/* ── Form elements ──────────────────────────── */
		.ttp-label {
			display:block;font-size:12px;font-weight:600;color:#555;margin-bottom:4px;
		}
		.ttp-input {
			width:100%;padding:6px 9px;border:1px solid #d1d8dd;border-radius:4px;
			font-size:13px;box-sizing:border-box;outline:none;
			transition:border-color .15s;
		}
		.ttp-input:focus { border-color:#c84630; }
		.ttp-field-row { display:flex;gap:14px; }
		.ttp-field { flex:1; }

		/* Toggle switch */
		.ttp-toggle { position:relative;display:inline-flex;align-items:center;cursor:pointer;height:20px; }
		.ttp-toggle input { opacity:0;width:0;height:0; }
		.ttp-slider {
			width:36px;height:20px;background:#ccc;border-radius:10px;
			transition:.25s;position:relative;display:inline-block;
		}
		.ttp-slider::before {
			content:"";position:absolute;height:14px;width:14px;left:3px;bottom:3px;
			background:#fff;border-radius:50%;transition:.25s;
		}
		.ttp-toggle input:checked + .ttp-slider { background:#c84630; }
		.ttp-toggle input:checked + .ttp-slider::before { transform:translateX(16px); }

		/* Checkbox row */
		.ttp-check-row {
			display:flex;align-items:center;gap:6px;font-size:12px;color:#444;cursor:pointer;
		}
		.ttp-check-row input { accent-color:#c84630;cursor:pointer; }

		/* Attach widget */
		.ttp-attach-wrap {
			border:1.5px dashed #d1d8dd;border-radius:6px;padding:8px;
			display:flex;flex-direction:column;align-items:center;min-height:80px;
			cursor:pointer;background:#fafafa;transition:border-color .15s;
		}
		.ttp-attach-wrap:hover { border-color:#c84630; }
		.ttp-attach-placeholder { display:flex;flex-direction:column;align-items:center;justify-content:center;padding:8px; }
		.ttp-attach-btn {
			font-size:11px;padding:3px 10px;border:1px solid #c84630;color:#c84630;
			border-radius:4px;background:white;cursor:pointer;
		}
		.ttp-attach-btn:hover { background:#fdf0ee; }
		.ttp-clear-btn {
			font-size:11px;padding:3px 10px;border:1px solid #ccc;color:#888;
			border-radius:4px;background:white;cursor:pointer;
		}
		.ttp-clear-btn:hover { border-color:#dc3545;color:#dc3545; }

		/* Accordion */
		.ttp-accordion {
			border:1px solid #e4e7ea;border-radius:8px;overflow:hidden;margin-bottom:10px;
		}
		.ttp-accordion-header {
			display:flex;align-items:center;justify-content:space-between;
			padding:12px 16px;cursor:pointer;background:#fff;user-select:none;
			transition:background .15s;
		}
		.ttp-accordion-header:hover { background:#fdf5f5; }
		.ttp-accordion-header-left { display:flex;align-items:center;gap:10px; }
		.ttp-accordion-title { font-size:13px;font-weight:600;color:#333; }
		.ttp-accordion-chevron {
			transition:transform .2s;color:#888;
			display:flex;align-items:center;
		}
		.ttp-accordion-chevron.open { transform:rotate(180deg); }
		.ttp-accordion-body { padding:14px 16px;border-top:1px solid #f0f0f0;background:#fff;display:none; }
		.ttp-accordion-body.open { display:block; }

		/* Signature row */
		.ttp-sig-row { display:flex;gap:10px;align-items:flex-end; }
		.ttp-sig-preview {
			width:80px;height:40px;border:1px dashed #ddd;border-radius:4px;
			display:flex;align-items:center;justify-content:center;font-size:10px;color:#ccc;
			overflow:hidden;flex-shrink:0;
		}
		.ttp-sig-preview img { max-width:100%;max-height:100%;object-fit:contain; }

		/* Preview panel */
		#ttp-preview-content {
			background:#fff;border-radius:4px;
			box-shadow:0 1px 8px rgba(0,0,0,.08);
			font-family:Georgia,serif;font-size:11px;
			min-height:480px;padding:20px;
		}
		</style>
	`);

	// ── Template helpers (generate HTML strings before page renders) ───────────

	function accordion_section(id, title, body_html) {
		const icons = {
			institute_logo:     `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
			institute_address:  `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
			basic_details:      `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
			signature_settings: `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
			watermark_logo:     `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>`,
		};
		return `
			<div class="ttp-accordion" id="acc-${id}">
				<div class="ttp-accordion-header" data-acc="${id}">
					<div class="ttp-accordion-header-left">
						${icons[id] || ""}
						<span class="ttp-accordion-title">${__(title)}</span>
					</div>
					<span class="ttp-accordion-chevron">
						<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="6 9 12 15 18 9"/>
						</svg>
					</span>
				</div>
				<div class="ttp-accordion-body" id="acc-body-${id}">
					${body_html}
				</div>
			</div>`;
	}

	function signature_row(n) {
		return `
			<div class="ttp-sig-row" id="sig-row-${n}">
				<div class="ttp-sig-preview" id="sig-img-preview-${n}">
					<img id="sig-img-${n}" src="" style="display:none;"/>
					<span class="sig-placeholder-text">${__("Sig")} ${n}</span>
				</div>
				<div style="flex:1;">
					<label class="ttp-label">${__("Signature")} ${n} – ${__("Label")}</label>
					<input id="cfg-sig_label_${n}" type="text" class="ttp-input"
						placeholder="${["Registrar","Controller of Examinations","Vice Chancellor"][n-1]}"/>
				</div>
				<div>
					<label class="ttp-label">${__("Image")}</label>
					<div style="display:flex;gap:4px;align-items:center;">
						<button class="ttp-attach-btn" data-sig="${n}">${__("Upload")}</button>
						<button class="ttp-clear-btn" data-sig-clear="${n}">${__("✕")}</button>
					</div>
					<input id="cfg-sig_image_${n}-file" type="file" accept="image/*" style="display:none;" data-sig="${n}"/>
					<input id="cfg-sig_image_${n}" type="hidden"/>
				</div>
			</div>`;
	}

	// ── Event wiring ───────────────────────────────────────────────────────────

	// Back to transcript-management-page
	$(wrapper).on("click", "#ttp-back-btn", () => {
		frappe.set_route("transcript-management-page");
	});

	// Add template
	$(wrapper).on("click", "#ttp-add-btn", () => open_configure(null));

	// Back from configure → list
	$(wrapper).on("click", "#ttp-cfg-back", () => show_list());

	// Accordion toggle
	$(wrapper).on("click", ".ttp-accordion-header", function () {
		const id   = $(this).data("acc");
		const body = $(`#acc-body-${id}`);
		body.toggleClass("open");
		$(this).find(".ttp-accordion-chevron").toggleClass("open");
	});

	// Watermark opacity label
	$(wrapper).on("input", "#cfg-watermark_opacity", function () {
		$(wrapper).find("#cfg-watermark_opacity-val").text($(this).val() + "%");
	});

	// Image upload handlers (logo + watermark)
	["institute_logo", "watermark_logo"].forEach(field => {
		$(wrapper).on("change", `#cfg-${field}`, function () {
			const file = this.files[0];
			if (!file) return;
			const reader = new FileReader();
			reader.onload = e => {
				const src = e.target.result;
				$(wrapper).find(`#cfg-${field}-preview`).attr("src", src).show();
				$(wrapper).find(`#cfg-${field}-placeholder`).hide();
				$(wrapper).find(`#cfg-${field}-url`).val(src);
				state.current = state.current || {};
				state.current[field] = src;
				refresh_preview();
			};
			reader.readAsDataURL(file);
		});
		$(wrapper).on("click", `#cfg-${field}-wrap`, function (e) {
			if ($(e.target).is("button")) return;
			$(wrapper).find(`#cfg-${field}`).click();
		});
		$(wrapper).on("click", `#cfg-${field}-clear`, function (e) {
			e.stopPropagation();
			$(wrapper).find(`#cfg-${field}-preview`).attr("src", "").hide();
			$(wrapper).find(`#cfg-${field}-placeholder`).show();
			$(wrapper).find(`#cfg-${field}`).val("");
			if (state.current) { state.current[field] = ""; }
			refresh_preview();
		});
	});

	// Signature upload
	$(wrapper).on("click", "[data-sig]", function () {
		const n = $(this).data("sig");
		$(wrapper).find(`#cfg-sig_image_${n}-file`).click();
	});
	$(wrapper).on("change", "[id^='cfg-sig_image_'][id$='-file']", function () {
		const n = $(this).data("sig");
		const file = this.files[0];
		if (!file) return;
		const reader = new FileReader();
		reader.onload = e => {
			const src = e.target.result;
			$(wrapper).find(`#sig-img-${n}`).attr("src", src).show();
			$(wrapper).find(`#sig-row-${n} .sig-placeholder-text`).hide();
			$(wrapper).find(`#cfg-sig_image_${n}`).val(src);
			if (state.current) state.current[`sig_image_${n}`] = src;
		};
		reader.readAsDataURL(file);
	});
	$(wrapper).on("click", "[data-sig-clear]", function () {
		const n = $(this).data("sig-clear");
		$(wrapper).find(`#sig-img-${n}`).attr("src", "").hide();
		$(wrapper).find(`#sig-row-${n} .sig-placeholder-text`).show();
		$(wrapper).find(`#cfg-sig_image_${n}-file`).val("");
		$(wrapper).find(`#cfg-sig_image_${n}`).val("");
		if (state.current) state.current[`sig_image_${n}`] = "";
	});

	// Live preview on form change
	$(wrapper).on("input change", "#ttp-cfg-form input, #ttp-cfg-form select, #ttp-cfg-form textarea", function () {
		clearTimeout(state._previewTimer);
		state._previewTimer = setTimeout(refresh_preview, 300);
	});

	// Refresh preview button
	$(wrapper).on("click", "#ttp-refresh-preview", refresh_preview);

	// Save
	$(wrapper).on("click", "#ttp-cfg-save", do_save);

	// Set default
	$(wrapper).on("click", "#ttp-cfg-set-default", function () {
		if (!state.current || !state.current.name) {
			frappe.msgprint(__("Please save the template first."));
			return;
		}
		frappe.call({
			method: API.set_default,
			args:   { name: state.current.name },
			callback(r) {
				if (r.message && r.message.success) {
					frappe.show_alert({ message: __("Default template updated."), indicator: "green" }, 3);
					$(wrapper).find("#ttp-cfg-set-default")
						.css({ "border-color": "#1e7e34", color: "#1e7e34" })
						.text(__("✓ Default"));
				}
			},
		});
	});

	// Search
	let _searchTimer;
	$(wrapper).on("input", "#ttp-search", function () {
		clearTimeout(_searchTimer);
		_searchTimer = setTimeout(() => {
			state.search = $(this).val().trim();
			load_templates();
		}, 300);
	});

	// Card click → configure
	$(wrapper).on("click", ".ttp-card", function (e) {
		if ($(e.target).closest(".ttp-action-btn").length) return;
		const name = $(this).data("name");
		open_configure(name);
	});

	// Card action: set default
	$(wrapper).on("click", ".btn-card-default", function (e) {
		e.stopPropagation();
		const name = $(this).closest(".ttp-card").data("name");
		frappe.call({
			method: API.set_default,
			args:   { name },
			callback(r) {
				if (r.message && r.message.success) {
					frappe.show_alert({ message: __("Default updated."), indicator: "green" }, 3);
					load_templates();
				}
			},
		});
	});

	// Card action: delete
	$(wrapper).on("click", ".btn-card-delete", function (e) {
		e.stopPropagation();
		const name = $(this).closest(".ttp-card").data("name");
		const type = $(this).closest(".ttp-card").data("type");
		if (type === "System") {
			frappe.msgprint({ title: __("Not Allowed"), message: __("System templates cannot be deleted."), indicator: "orange" });
			return;
		}
		frappe.confirm(
			__("Delete template <b>{0}</b>? This cannot be undone.", [name]),
			() => {
				frappe.call({
					method: API.delete_template,
					args:   { name },
					callback(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({ message: __("Template deleted."), indicator: "green" }, 3);
							load_templates();
						}
					},
				});
			}
		);
	});

	// ── Core functions ─────────────────────────────────────────────────────────

	function show_list() {
		state.view = "list";
		$(wrapper).find("#ttp-list-view").show();
		$(wrapper).find("#ttp-configure-view").hide();
	}

	function show_configure() {
		state.view = "configure";
		$(wrapper).find("#ttp-list-view").hide();
		$(wrapper).find("#ttp-configure-view").show();
	}

	function load_templates() {
		const grid = $(wrapper).find("#ttp-cards-grid");
		grid.html(`<div style="text-align:center;padding:60px;color:#aaa;grid-column:1/-1;">
			<div class="ttp-spinner" style="margin:0 auto 10px;"></div>${__("Loading…")}</div>`);

		frappe.call({
			method: API.get_templates,
			args:   { search: state.search },
			callback(r) {
				if (!r.message) return;
				state.templates = r.message.templates || [];
				render_cards(state.templates);
			},
			error() {
				grid.html(`<div style="text-align:center;padding:40px;color:#c84630;grid-column:1/-1;">
					${__("Error loading templates. Please refresh.")}</div>`);
			},
		});
	}

	function render_cards(templates) {
		const grid = $(wrapper).find("#ttp-cards-grid");
		if (!templates.length) {
			grid.html(`<div style="text-align:center;padding:60px;color:#aaa;grid-column:1/-1;">
				<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none"
					stroke="#ddd" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
					style="display:block;margin:0 auto 10px;">
					<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
					<polyline points="14 2 14 8 20 8"/>
				</svg>
				${__("No templates found.")}
				<div style="margin-top:10px;">
					<button class="btn btn-sm" style="background:#c84630;color:white;border:none;" id="ttp-add-btn-empty">
						${__("+ Add Template")}
					</button>
				</div>
			</div>`);
			$(wrapper).on("click", "#ttp-add-btn-empty", () => open_configure(null));
			return;
		}

		const cards = templates.map(t => {
			const thumb   = build_thumb_svg(t);
			const badge   = t.template_type === "System"
				? `<span class="ttp-badge ttp-badge-system">${__("System")}</span>`
				: `<span class="ttp-badge ttp-badge-custom">${__("Custom")}</span>`;
			const defBadge = t.is_default
				? `<span class="ttp-badge ttp-badge-default">${__("Default")}</span>`
				: "";
			const modDate  = t.modified ? frappe.datetime.str_to_user(t.modified).split(" ")[0] : "";
			const modBy    = frappe.utils.escape_html(t.modified_by || "—");
			const canDelete = t.template_type !== "System";

			return `
				<div class="ttp-card" data-name="${frappe.utils.escape_html(t.name)}" data-type="${t.template_type}">
					<div class="ttp-card-thumb">
						${thumb}
						<div class="ttp-card-actions">
							<button class="ttp-action-btn btn-card-default" title="${__('Set as Default')}">
								${__("Default")}
							</button>
							${canDelete ? `<button class="ttp-action-btn danger btn-card-delete" title="${__('Delete')}">
								${__("Delete")}
							</button>` : ""}
						</div>
					</div>
					<div class="ttp-card-body">
						<div class="ttp-card-title">${frappe.utils.escape_html(t.template_name)}</div>
						<div class="ttp-card-meta" style="margin-bottom:6px;">
							${badge}${defBadge}
							<span style="margin-left:4px;">${__("Page")} : ${t.page_size || "A4"} | ${__("Mode")} : ${t.orientation || "Portrait"}</span>
						</div>
						<div class="ttp-card-meta" style="color:#aaa;font-size:10px;">
							${modBy} &nbsp;·&nbsp; ${modDate}
						</div>
					</div>
				</div>`;
		});

		grid.html(cards.join(""));
	}

	function build_thumb_svg(t) {
		// Mini SVG mockup of the transcript layout — portrait vs landscape
		const isLandscape = (t.orientation || "Portrait") === "Landscape";
		const w = isLandscape ? 200 : 140;
		const h = isLandscape ? 140 : 180;

		return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg"
			style="width:${w*0.85}px;height:${h*0.85}px;filter:drop-shadow(0 2px 6px rgba(0,0,0,.12));">
			<!-- Page background -->
			<rect width="${w}" height="${h}" fill="white" rx="3" stroke="#e0e0e0" stroke-width="1"/>
			<!-- Header band -->
			<rect x="0" y="0" width="${w}" height="${isLandscape ? 24 : 28}" fill="#c84630" rx="3"/>
			<rect x="0" y="${isLandscape ? 20 : 24}" width="${w}" height="${isLandscape ? 4 : 4}" fill="#c84630"/>
			<!-- Logo placeholder -->
			<circle cx="${isLandscape ? 16 : 14}" cy="${isLandscape ? 12 : 14}" r="${isLandscape ? 8 : 9}" fill="rgba(255,255,255,.25)"/>
			<!-- Title lines -->
			<rect x="${isLandscape ? 30 : 28}" y="${isLandscape ? 8 : 9}" width="${isLandscape ? 80 : 70}" height="5" fill="rgba(255,255,255,.7)" rx="2"/>
			<rect x="${isLandscape ? 30 : 28}" y="${isLandscape ? 16 : 16}" width="${isLandscape ? 55 : 45}" height="3" fill="rgba(255,255,255,.4)" rx="1"/>
			<!-- Student info block -->
			<rect x="8" y="${isLandscape ? 32 : 36}" width="${isLandscape ? 55 : 50}" height="4" fill="#e8eaed" rx="1"/>
			<rect x="8" y="${isLandscape ? 39 : 43}" width="${isLandscape ? 40 : 35}" height="3" fill="#f1f3f4" rx="1"/>
			<rect x="8" y="${isLandscape ? 45 : 49}" width="${isLandscape ? 48 : 42}" height="3" fill="#f1f3f4" rx="1"/>
			<!-- Table header -->
			<rect x="8" y="${isLandscape ? 56 : 60}" width="${w - 16}" height="7" fill="#f8f0ef" rx="1"/>
			<rect x="8" y="${isLandscape ? 56 : 60}" width="${isLandscape ? 65 : 55}" height="7" fill="#fce8e6" rx="1"/>
			<!-- Table rows -->
			${[0,1,2,3,4].map(i => {
				const y = (isLandscape ? 66 : 70) + i * (isLandscape ? 10 : 11);
				return `<rect x="8" y="${y}" width="${w - 16}" height="6" fill="${i % 2 === 0 ? '#fafafa' : '#fff'}" rx="1" stroke="#f0f0f0" stroke-width=".5"/>
				<rect x="8" y="${y}" width="${isLandscape ? 65 : 55}" height="6" fill="none" stroke="#f0f0f0" stroke-width=".5"/>`;
			}).join("")}
			<!-- Footer line -->
			<line x1="8" y1="${h - 14}" x2="${w - 8}" y2="${h - 14}" stroke="#e0e0e0" stroke-width=".8"/>
			<rect x="8" y="${h - 11}" width="28" height="3" fill="#e8eaed" rx="1"/>
			<rect x="${w/2 - 14}" y="${h - 11}" width="28" height="3" fill="#e8eaed" rx="1"/>
			<rect x="${w - 36}" y="${h - 11}" width="28" height="3" fill="#e8eaed" rx="1"/>
		</svg>`;
	}

	function open_configure(name) {
		if (name) {
			frappe.call({
				method: API.get_template,
				args:   { name },
				freeze: true,
				freeze_message: __("Loading template…"),
				callback(r) {
					if (!r.message) return;
					state.current = r.message;
					show_configure();
					populate_form(r.message);
					refresh_preview();
				},
				error() {
					frappe.msgprint({
						title:     __("Error"),
						message:   __("Could not load template '{0}'. Please try again.", [name]),
						indicator: "red",
					});
				},
			});
		} else {
			// New template
			state.current = { template_type: "Custom", page_size: "A4", orientation: "Portrait" };
			show_configure();
			populate_form(state.current);
			refresh_preview();
		}
	}

	function populate_form(data) {
		const f = field => $(wrapper).find(`#cfg-${field}`);

		// Title
		$(wrapper).find("#ttp-cfg-title").text(
			data.name ? __("Configure: {0}", [data.template_name || data.name]) : __("New Template")
		);

		// Update Set Default button label
		$(wrapper).find("#ttp-cfg-set-default")
			.css({ "border-color": data.is_default ? "#1e7e34" : "", color: data.is_default ? "#1e7e34" : "" })
			.text(data.is_default ? __("✓ Default") : __("Set as Default"));

		// Scalar fields
		[
			"template_name", "template_type", "page_size", "orientation",
			"institute_name", "institute_address", "institute_city", "institute_country",
			"header_title", "watermark_text", "logo_width",
		].forEach(field => {
			const val = data[field];
			if (val !== undefined && val !== null) f(field).val(val);
		});

		// Selects
		f("logo_alignment").val(data.logo_alignment || "Center");

		// Checkboxes
		[
			"show_institute_logo", "show_institute_address",
			"show_student_photo", "show_registration_id",
			"show_cgpa", "show_credits", "show_semester_wise",
			"show_watermark",
		].forEach(field => {
			f(field).prop("checked", !!data[field]);
		});

		// Range
		const opacity = data.watermark_opacity || 15;
		f("watermark_opacity").val(opacity);
		$(wrapper).find("#cfg-watermark_opacity-val").text(opacity + "%");

		// Logo image
		set_image_field("institute_logo", data.institute_logo);
		set_image_field("watermark_logo",  data.watermark_logo);

		// Signatures
		[1, 2, 3].forEach(n => {
			f(`sig_label_${n}`).val(data[`sig_label_${n}`] || "");
			const src = data[`sig_image_${n}`] || "";
			$(wrapper).find(`#cfg-sig_image_${n}`).val(src);
			if (src) {
				$(wrapper).find(`#sig-img-${n}`).attr("src", src).show();
				$(wrapper).find(`#sig-row-${n} .sig-placeholder-text`).hide();
			} else {
				$(wrapper).find(`#sig-img-${n}`).attr("src", "").hide();
				$(wrapper).find(`#sig-row-${n} .sig-placeholder-text`).show();
			}
		});

		// Open first accordion by default
		$(wrapper).find(".ttp-accordion-body.open").removeClass("open");
		$(wrapper).find(".ttp-accordion-chevron.open").removeClass("open");
		$(wrapper).find("#acc-body-institute_logo").addClass("open");
		$(wrapper).find("#acc-institute_logo .ttp-accordion-chevron").addClass("open");
	}

	function set_image_field(field, src) {
		if (src) {
			$(wrapper).find(`#cfg-${field}-preview`).attr("src", src).show();
			$(wrapper).find(`#cfg-${field}-placeholder`).hide();
		} else {
			$(wrapper).find(`#cfg-${field}-preview`).attr("src", "").hide();
			$(wrapper).find(`#cfg-${field}-placeholder`).show();
		}
	}

	function collect_form_data() {
		const f   = field => $(wrapper).find(`#cfg-${field}`);
		const chk = field => f(field).is(":checked") ? 1 : 0;

		return {
			name:                    state.current && state.current.name ? state.current.name : f("template_name").val().trim(),
			template_name:           f("template_name").val().trim(),
			template_type:           f("template_type").val(),
			page_size:               f("page_size").val(),
			orientation:             f("orientation").val(),
			institute_logo:          f("institute_logo-preview").attr("src") || "",
			show_institute_logo:     chk("show_institute_logo"),
			logo_alignment:          f("logo_alignment").val(),
			logo_width:              parseInt(f("logo_width").val()) || 120,
			institute_name:          f("institute_name").val().trim(),
			institute_address:       f("institute_address").val().trim(),
			show_institute_address:  chk("show_institute_address"),
			institute_city:          f("institute_city").val().trim(),
			institute_country:       f("institute_country").val().trim(),
			header_title:            f("header_title").val().trim(),
			show_student_photo:      chk("show_student_photo"),
			show_registration_id:    chk("show_registration_id"),
			show_cgpa:               chk("show_cgpa"),
			show_credits:            chk("show_credits"),
			show_semester_wise:      chk("show_semester_wise"),
			sig_label_1:             f("sig_label_1").val().trim(),
			sig_image_1:             f("sig_image_1").val(),
			sig_label_2:             f("sig_label_2").val().trim(),
			sig_image_2:             f("sig_image_2").val(),
			sig_label_3:             f("sig_label_3").val().trim(),
			sig_image_3:             f("sig_image_3").val(),
			watermark_logo:          f("watermark_logo-preview").attr("src") || "",
			show_watermark:          chk("show_watermark"),
			watermark_text:          f("watermark_text").val().trim(),
			watermark_opacity:       parseInt(f("watermark_opacity").val()) || 15,
		};
	}

	function do_save() {
		const data = collect_form_data();
		if (!data.template_name) {
			frappe.show_alert({ message: __("Template Name is required."), indicator: "red" }, 4);
			$(wrapper).find("#cfg-template_name").focus();
			return;
		}

		const btn = $(wrapper).find("#ttp-cfg-save").prop("disabled", true).text(__("Saving…"));

		frappe.call({
			method:  API.save_template,
			args:    { data: JSON.stringify(data) },
			callback(r) {
				btn.prop("disabled", false).text(__("Save"));
				if (!r.message) return;
				state.current = r.message;
				$(wrapper).find("#ttp-cfg-title").text(__("Configure: {0}", [r.message.template_name]));
				frappe.show_alert({ message: __("Template '{0}' saved.", [r.message.template_name]), indicator: "green" }, 4);
			},
			error(r) {
				btn.prop("disabled", false).text(__("Save"));
				const msg = (r && r.message) ? r.message : __("Failed to save. Please try again.");
				frappe.msgprint({ title: __("Save Error"), message: msg, indicator: "red" });
			},
		});
	}

	function refresh_preview() {
		const data   = collect_form_data();
		const isLand = data.orientation === "Landscape";
		const pw     = isLand ? "100%" : "75%";
		const ratio  = isLand ? "70.7%" : "141.4%";  // A4 aspect

		const logoHtml = (data.show_institute_logo && data.institute_logo)
			? `<img src="${data.institute_logo}" style="max-height:${data.logo_width ? data.logo_width*0.35 : 42}px;max-width:140px;object-fit:contain;"/>`
			: `<div style="width:42px;height:42px;background:rgba(255,255,255,.25);border-radius:50%;display:inline-block;"></div>`;

		const headerTitle = frappe.utils.escape_html(data.header_title || "OFFICIAL TRANSCRIPT OF ACADEMIC RECORDS");
		const instName    = frappe.utils.escape_html(data.institute_name || "Institute Name");
		const instAddr    = (data.show_institute_address && data.institute_address)
			? frappe.utils.escape_html([data.institute_address, data.institute_city, data.institute_country].filter(Boolean).join(", "))
			: "";

		const sigs = [1,2,3].map(n => {
			const lbl = frappe.utils.escape_html(data[`sig_label_${n}`] || "");
			const img = data[`sig_image_${n}`]
				? `<img src="${data[`sig_image_${n}`]}" style="height:18px;margin-bottom:2px;"/><br/>`
				: `<div style="width:50px;height:16px;border-bottom:1px solid #999;margin-bottom:2px;"></div>`;
			return lbl ? `<div style="text-align:center;font-size:9px;">${img}<span style="font-size:9px;color:#555;">${lbl}</span></div>` : "";
		}).filter(Boolean).join("");

		const watermarkHtml = (data.show_watermark && (data.watermark_logo || data.watermark_text))
			? `<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%) rotate(-30deg);
				opacity:${(data.watermark_opacity || 15)/100};pointer-events:none;z-index:0;font-size:28px;
				font-weight:900;color:#c84630;white-space:nowrap;">
				${data.watermark_text || "WATERMARK"}</div>`
			: "";

		const tableRows = Array.from({ length: 4 }, (_, i) => `
			<tr style="background:${i % 2 === 0 ? "#fafafa" : "#fff"}">
				<td style="padding:3px 6px;border:1px solid #eee;font-size:9px;color:#666;">Sample Course ${i + 1}</td>
				<td style="padding:3px 6px;border:1px solid #eee;font-size:9px;text-align:center;">${3 + i}</td>
				<td style="padding:3px 6px;border:1px solid #eee;font-size:9px;text-align:center;">A</td>
				<td style="padding:3px 6px;border:1px solid #eee;font-size:9px;text-align:center;">9.0</td>
			</tr>`).join("");

		$(wrapper).find("#ttp-preview-content").html(`
			<div style="width:${pw};margin:0 auto;position:relative;font-family:Georgia,serif;">
				<div style="padding-top:${ratio};position:relative;">
				<div style="position:absolute;inset:0;background:white;border:1px solid #ddd;
					border-radius:3px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.1);">
					${watermarkHtml}
					<!-- Header -->
					<div style="background:#c84630;padding:10px 14px;display:flex;align-items:center;
						gap:10px;min-height:${isLand ? "36px" : "48px"};">
						<div style="text-align:${data.logo_alignment ? data.logo_alignment.toLowerCase() : "center"};flex-shrink:0;">
							${logoHtml}
						</div>
						<div style="flex:1;">
							<div style="font-size:${isLand ? "10px" : "11px"};font-weight:700;color:white;letter-spacing:.5px;">
								${instName}
							</div>
							<div style="font-size:${isLand ? "8px" : "9px"};color:rgba(255,255,255,.8);margin-top:2px;">
								${headerTitle}
							</div>
							${instAddr ? `<div style="font-size:8px;color:rgba(255,255,255,.65);margin-top:2px;">${instAddr}</div>` : ""}
						</div>
					</div>
					<!-- Student info -->
					<div style="padding:8px 12px;display:flex;gap:10px;border-bottom:1px solid #f0f0f0;">
						${data.show_student_photo ? `<div style="width:32px;height:38px;background:#e8eaed;border-radius:2px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:9px;color:#aaa;">Photo</div>` : ""}
						<div style="flex:1;">
							<div style="font-size:11px;font-weight:700;color:#222;">Student Name Here</div>
							${data.show_registration_id ? `<div style="font-size:9px;color:#777;">Reg. ID: REG2024001</div>` : ""}
							<div style="font-size:9px;color:#777;">Programme: B.A. LL.B (Hons.)</div>
							<div style="font-size:9px;color:#777;">Batch: 2020–2025</div>
						</div>
						${data.show_cgpa ? `<div style="text-align:right;"><div style="font-size:9px;color:#888;">CGPA</div><div style="font-size:16px;font-weight:700;color:#c84630;">8.52</div></div>` : ""}
					</div>
					<!-- Course table -->
					<div style="padding:6px 12px;">
						${data.show_semester_wise ? `<div style="font-size:9px;font-weight:700;color:#c84630;margin-bottom:4px;">SEMESTER I</div>` : ""}
						<table style="width:100%;border-collapse:collapse;font-size:9px;">
							<thead>
								<tr style="background:#fce8e6;">
									<th style="padding:3px 6px;text-align:left;border:1px solid #eee;font-size:9px;">Course</th>
									<th style="padding:3px 6px;border:1px solid #eee;font-size:9px;">${data.show_credits ? "Cr" : ""}</th>
									<th style="padding:3px 6px;border:1px solid #eee;font-size:9px;">Grade</th>
									<th style="padding:3px 6px;border:1px solid #eee;font-size:9px;">GP</th>
								</tr>
							</thead>
							<tbody>${tableRows}</tbody>
						</table>
					</div>
					<!-- Footer signatures -->
					${sigs ? `<div style="position:absolute;bottom:6px;left:12px;right:12px;display:flex;justify-content:space-around;">${sigs}</div>` : ""}
				</div>
				</div>
			</div>
		`);
	}

	// ── Initial load ───────────────────────────────────────────────────────────

	// Seed built-in templates if needed, then load list
	frappe.call({
		method:   API.seed_default_templates,
		callback() { load_templates(); },
		error()   { load_templates(); },  // Still load even if seed fails
	});
};
