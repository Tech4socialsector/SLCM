// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.pages["transcript-template-page"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Transcript Templates"),
		single_column: true,
	});

	// ── API paths ──────────────────────────────────────────────────────────────
	const API = {
		get_templates:          "slcm.slcm.page.transcript_template_page.transcript_template_page.get_templates",
		get_template:           "slcm.slcm.page.transcript_template_page.transcript_template_page.get_template",
		save_template:          "slcm.slcm.page.transcript_template_page.transcript_template_page.save_template",
		delete_template:        "slcm.slcm.page.transcript_template_page.transcript_template_page.delete_template",
		set_default:            "slcm.slcm.page.transcript_template_page.transcript_template_page.set_default",
		seed_default_templates: "slcm.slcm.page.transcript_template_page.transcript_template_page.seed_default_templates",
	};

	// ── State ──────────────────────────────────────────────────────────────────
	const state = {
		view:            "list",   // "list" | "configure"
		templates:       [],
		current:         null,     // doc dict being edited
		meta:            null,     // cached Transcript Template meta
		field_controls:  {},       // fieldname → { get_value(), set_value(v) }
		_preview_timer:  null,
		_search_timer:   null,
	};

	// ── Section icon map (label → SVG string) ─────────────────────────────────
	// Keys match section Break labels in the doctype. New sections get a default icon.
	const SECTION_ICON = {
		"Institute Logo": `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
		"Institute Address": `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
		"Basic Details": `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
		"Signature Settings": `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
		"Watermark Logo": `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>`,
		"Additional Info": `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
		_default: `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#c84630" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>`,
	};

	// ── Page HTML skeleton ─────────────────────────────────────────────────────
	// The configure form (#ttp-cfg-form) is rendered dynamically from doctype meta.
	$(wrapper).find(".page-content").html(`
		<div id="ttp-root" style="padding:16px;">

			<!-- LIST VIEW -->
			<div id="ttp-list-view">
				<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:20px;">
					<div style="position:relative;flex:1;min-width:220px;max-width:400px;">
						<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
							fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
							style="position:absolute;left:10px;top:50%;transform:translateY(-50%);">
							<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
						</svg>
						<input id="ttp-search" type="text" placeholder="${__("Search templates…")}"
							style="width:100%;padding:7px 10px 7px 32px;border:1px solid #d1d8dd;border-radius:5px;
							font-size:13px;outline:none;box-sizing:border-box;"/>
					</div>
					<div style="margin-left:auto;display:flex;gap:8px;align-items:center;">
						<button id="ttp-back-btn" class="btn btn-default btn-sm ttp-outline-btn">
							← ${__("Back to Students")}
						</button>
						<button id="ttp-add-btn" class="btn btn-sm ttp-primary-btn">
							+ ${__("Add Template")}
						</button>
					</div>
				</div>
				<div id="ttp-cards-grid" class="ttp-cards-grid">
					<div class="ttp-center-msg"><div class="ttp-spinner"></div>${__("Loading…")}</div>
				</div>
			</div>

			<!-- CONFIGURE VIEW (form populated at run-time via doctype meta) -->
			<div id="ttp-configure-view" style="display:none;">
				<!-- Header -->
				<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;
				            padding-bottom:14px;border-bottom:2px solid #f0f0f0;flex-wrap:wrap;">
					<button id="ttp-cfg-back" class="btn btn-xs ttp-outline-btn"
						style="display:flex;align-items:center;gap:4px;">
						← ${__("Back")}
					</button>
					<div>
						<div id="ttp-cfg-title" style="font-size:17px;font-weight:700;color:#222;">
							${__("Configure Template")}
						</div>
						<div style="font-size:12px;color:#888;margin-top:1px;">
							${__("Configure the settings as per your need")}
						</div>
					</div>
					<div style="margin-left:auto;display:flex;gap:8px;">
						<button id="ttp-cfg-set-default" class="btn btn-sm btn-default"
							style="border-color:#6c757d;color:#6c757d;min-width:110px;">
							${__("Set as Default")}
						</button>
						<button id="ttp-cfg-save" class="btn btn-sm ttp-primary-btn" style="min-width:80px;">
							${__("Save")}
						</button>
					</div>
				</div>

				<!-- Two-column: form left, preview right -->
				<div style="display:flex;gap:20px;align-items:flex-start;">
					<div id="ttp-cfg-form" style="flex:0 0 460px;min-width:280px;max-width:520px;">
						<div class="ttp-center-msg"><div class="ttp-spinner"></div>${__("Loading fields…")}</div>
					</div>
					<div style="flex:1;position:sticky;top:70px;">
						<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
							<span style="font-size:12px;font-weight:600;color:#555;">${__("Preview")}</span>
							<button id="ttp-refresh-preview" class="btn btn-xs btn-default"
								style="font-size:11px;display:flex;align-items:center;gap:4px;">
								↺ ${__("Refresh")}
							</button>
						</div>
						<div style="border:1px solid #e4e7ea;border-radius:6px;overflow:hidden;
						            background:#f9fafb;min-height:500px;">
							<div id="ttp-preview-content" style="padding:12px;"></div>
						</div>
						<div style="font-size:11px;color:#aaa;margin-top:6px;text-align:center;">
							${__("Preview is approximate — actual PDF may differ slightly.")}
						</div>
					</div>
				</div>
			</div>
		</div>

		<style>
		.ttp-primary-btn  { background:#c84630;color:white;border:none; }
		.ttp-primary-btn:hover  { background:#a83820;color:white; }
		.ttp-primary-btn:disabled { background:#e0a090;cursor:not-allowed; }
		.ttp-outline-btn  { border:1px solid #c84630 !important;color:#c84630 !important;background:white !important; }
		.ttp-outline-btn:hover { background:#fdf0ee !important; }

		.ttp-cards-grid { display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:20px; }
		.ttp-center-msg  { text-align:center;padding:60px;color:#aaa;grid-column:1/-1; }
		.ttp-spinner     { width:28px;height:28px;border:3px solid #e4e7ea;border-top-color:#c84630;
		                   border-radius:50%;animation:ttp-spin .8s linear infinite;margin:0 auto 10px; }
		@keyframes ttp-spin { to { transform:rotate(360deg); } }

		/* Card */
		.ttp-card { background:#fff;border:1px solid #e4e7ea;border-radius:10px;overflow:hidden;
		            cursor:pointer;transition:box-shadow .18s,transform .18s; }
		.ttp-card:hover { box-shadow:0 4px 18px rgba(0,0,0,.12);transform:translateY(-2px); }
		.ttp-card-thumb  { background:#f4f6f8;height:160px;display:flex;align-items:center;
		                   justify-content:center;border-bottom:1px solid #f0f0f0;
		                   overflow:hidden;position:relative; }
		.ttp-card-body   { padding:14px 16px; }
		.ttp-card-title  { font-size:14px;font-weight:700;color:#222;margin-bottom:4px; }
		.ttp-card-meta   { font-size:11px;color:#888; }
		.ttp-card-actions { display:none;position:absolute;top:8px;right:8px;gap:4px; }
		.ttp-card-thumb:hover .ttp-card-actions { display:flex; }
		.ttp-action-btn  { background:rgba(255,255,255,.9);border:1px solid #ddd;border-radius:4px;
		                   padding:3px 8px;font-size:11px;cursor:pointer;color:#555; }
		.ttp-action-btn:hover         { background:#fff;color:#c84630;border-color:#c84630; }
		.ttp-action-btn.danger:hover  { color:#dc3545;border-color:#dc3545; }
		.ttp-badge         { display:inline-block;padding:1px 7px;border-radius:8px;font-size:10px;font-weight:600; }
		.ttp-badge-system  { background:#e8f0fe;color:#1a73e8; }
		.ttp-badge-custom  { background:#fce8e6;color:#c84630; }
		.ttp-badge-default { background:#e6f4ea;color:#1e7e34;margin-left:4px; }

		/* Form layout */
		.ttp-base-card   { background:#fff;border:1px solid #e4e7ea;border-radius:8px;padding:16px;margin-bottom:10px; }
		.ttp-base-grid   { display:grid;grid-template-columns:1fr 1fr;gap:12px; }
		.ttp-field-wrap  { margin-bottom:12px; }
		.ttp-field-wrap:last-child { margin-bottom:0; }
		.ttp-cols        { display:flex;gap:14px; }
		.ttp-col         { flex:1;min-width:0; }

		/* Labels + controls */
		.ttp-label       { display:block;font-size:12px;font-weight:600;color:#555;margin-bottom:4px; }
		.ttp-label .reqd { color:#c84630;margin-left:2px; }
		.ttp-desc        { font-size:11px;color:#aaa;margin-top:2px; }
		.ttp-control     { width:100%;padding:6px 9px;border:1px solid #d1d8dd;border-radius:4px;
		                   font-size:13px;box-sizing:border-box;outline:none;transition:border-color .15s;
		                   font-family:inherit;background:white; }
		.ttp-control:focus { border-color:#c84630; }
		.ttp-control:disabled { background:#f8f8f8;color:#aaa;cursor:not-allowed; }

		/* Toggle switch */
		.ttp-toggle-wrap { display:inline-flex;align-items:center;gap:8px;cursor:pointer;height:30px; }
		.ttp-toggle-wrap .ttp-toggle-label { font-size:12px;color:#555; }
		.ttp-toggle      { position:relative;width:36px;height:20px;flex-shrink:0; }
		.ttp-toggle input  { opacity:0;width:0;height:0;position:absolute; }
		.ttp-slider        { position:absolute;inset:0;background:#ccc;border-radius:10px;cursor:pointer;transition:.25s; }
		.ttp-slider::before { content:"";position:absolute;height:14px;width:14px;left:3px;bottom:3px;
		                      background:#fff;border-radius:50%;transition:.25s; }
		.ttp-toggle input:checked ~ .ttp-slider { background:#c84630; }
		.ttp-toggle input:checked ~ .ttp-slider::before { transform:translateX(16px); }

		/* Attach/Image upload widget */
		.ttp-attach-widget { border:1.5px dashed #d1d8dd;border-radius:6px;padding:10px;min-height:82px;
		                     background:#fafafa;cursor:pointer;display:flex;flex-direction:column;
		                     align-items:center;justify-content:center;transition:border-color .15s;
		                     position:relative;gap:4px; }
		.ttp-attach-widget:hover  { border-color:#c84630;background:#fdf5f5; }
		.ttp-attach-widget img    { max-height:60px;max-width:160px;object-fit:contain;border-radius:4px; }
		.ttp-attach-placeholder   { display:flex;flex-direction:column;align-items:center;
		                            font-size:11px;color:#aaa;gap:4px; }
		.ttp-attach-remove        { position:absolute;top:4px;right:4px;background:rgba(200,70,48,.85);
		                            color:white;border:none;border-radius:50%;width:18px;height:18px;
		                            cursor:pointer;font-size:10px;display:flex;align-items:center;
		                            justify-content:center;line-height:1;padding:0; }
		.ttp-attach-actions       { display:flex;gap:6px;margin-top:6px; }
		.ttp-btn-upload { font-size:11px;padding:3px 10px;border:1px solid #c84630;color:#c84630;
		                  border-radius:4px;background:white;cursor:pointer; }
		.ttp-btn-upload:hover { background:#fdf0ee; }
		.ttp-btn-clear  { font-size:11px;padding:3px 10px;border:1px solid #ccc;color:#888;
		                  border-radius:4px;background:white;cursor:pointer; }
		.ttp-btn-clear:hover { border-color:#dc3545;color:#dc3545; }

		/* Accordion */
		.ttp-accordion        { border:1px solid #e4e7ea;border-radius:8px;overflow:hidden;margin-bottom:10px; }
		.ttp-acc-header       { display:flex;align-items:center;justify-content:space-between;
		                        padding:12px 16px;cursor:pointer;background:#fff;user-select:none;
		                        transition:background .15s; }
		.ttp-acc-header:hover { background:#fdf5f5; }
		.ttp-acc-title        { font-size:13px;font-weight:600;color:#333; }
		.ttp-acc-icon         { display:flex;align-items:center;gap:8px; }
		.ttp-acc-chevron      { transition:transform .2s;color:#888;line-height:1;display:flex;align-items:center; }
		.ttp-acc-chevron.open { transform:rotate(180deg); }
		.ttp-acc-body         { padding:14px 16px;border-top:1px solid #f0f0f0;background:#fff;display:none; }
		.ttp-acc-body.open    { display:block; }
		</style>
	`);

	// ── Static event bindings ──────────────────────────────────────────────────

	$(wrapper).on("click", "#ttp-back-btn", () => frappe.set_route("transcript-management-page"));
	$(wrapper).on("click", "#ttp-add-btn",  () => open_configure(null));
	$(wrapper).on("click", "#ttp-cfg-back", () => show_list());
	$(wrapper).on("click", "#ttp-cfg-save", do_save);
	$(wrapper).on("click", "#ttp-refresh-preview", () => refresh_preview());
	$(wrapper).on("click", "#ttp-cfg-set-default", handle_set_default);

	// Accordion toggle (delegated — works after dynamic render)
	$(wrapper).on("click", ".ttp-acc-header", function () {
		const body     = $(this).next(".ttp-acc-body");
		const chevron  = $(this).find(".ttp-acc-chevron");
		body.toggleClass("open");
		chevron.toggleClass("open");
	});

	// Search
	$(wrapper).on("input", "#ttp-search", function () {
		clearTimeout(state._search_timer);
		state._search_timer = setTimeout(() => {
			state.search = $(this).val().trim();
			load_templates();
		}, 300);
	});

	// Card click → configure
	$(wrapper).on("click", ".ttp-card", function (e) {
		if ($(e.target).closest(".ttp-action-btn").length) return;
		open_configure($(this).data("name"));
	});

	// Card → set default
	$(wrapper).on("click", ".btn-card-default", function (e) {
		e.stopPropagation();
		const name = $(this).closest(".ttp-card").data("name");
		frappe.call({
			method: API.set_default, args: { name },
			callback(r) {
				if (r.message && r.message.success) {
					frappe.show_alert({ message: __("Default updated."), indicator: "green" }, 3);
					load_templates();
				}
			},
		});
	});

	// Card → delete
	$(wrapper).on("click", ".btn-card-delete", function (e) {
		e.stopPropagation();
		const name = $(this).closest(".ttp-card").data("name");
		const type = $(this).closest(".ttp-card").data("type");
		if (type === "System") {
			frappe.msgprint({ title: __("Not Allowed"), message: __("System templates cannot be deleted."), indicator: "orange" });
			return;
		}
		frappe.confirm(__("Delete template <b>{0}</b>? This cannot be undone.", [name]), () => {
			frappe.call({
				method: API.delete_template, args: { name },
				callback(r) {
					if (r.message && r.message.success) {
						frappe.show_alert({ message: __("Template deleted."), indicator: "green" }, 3);
						load_templates();
					}
				},
			});
		});
	});

	// ── List view ──────────────────────────────────────────────────────────────

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
		grid.html(`<div class="ttp-center-msg"><div class="ttp-spinner"></div>${__("Loading…")}</div>`);

		frappe.call({
			method: API.get_templates,
			args:   { search: state.search || "" },
			callback(r) {
				state.templates = (r && r.message && r.message.templates) || [];
				render_cards(state.templates);
			},
			error() {
				grid.html(`<div class="ttp-center-msg" style="color:#c84630;">${__("Error loading templates. Please refresh.")}</div>`);
			},
		});
	}

	function render_cards(templates) {
		const grid = $(wrapper).find("#ttp-cards-grid");
		if (!templates.length) {
			grid.html(`
				<div class="ttp-center-msg">
					<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24"
						fill="none" stroke="#ddd" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
						style="display:block;margin:0 auto 10px;">
						<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
						<polyline points="14 2 14 8 20 8"/>
					</svg>
					${__("No templates found.")}
					<div style="margin-top:12px;">
						<button class="btn btn-sm ttp-primary-btn" id="ttp-add-btn-empty">+ ${__("Add Template")}</button>
					</div>
				</div>`);
			$(wrapper).on("click", "#ttp-add-btn-empty", () => open_configure(null));
			return;
		}

		const html = templates.map(t => {
			const thumb    = build_thumb_svg(t);
			const badge    = t.template_type === "System"
				? `<span class="ttp-badge ttp-badge-system">${__("System")}</span>`
				: `<span class="ttp-badge ttp-badge-custom">${__("Custom")}</span>`;
			const defBadge = t.is_default
				? `<span class="ttp-badge ttp-badge-default">${__("Default")}</span>` : "";
			const modDate  = t.modified
				? frappe.datetime.str_to_user(t.modified).split(" ")[0] : "";
			const canDel   = t.template_type !== "System";

			return `
				<div class="ttp-card" data-name="${frappe.utils.escape_html(t.name)}" data-type="${t.template_type}">
					<div class="ttp-card-thumb">
						${thumb}
						<div class="ttp-card-actions">
							<button class="ttp-action-btn btn-card-default">${__("Set Default")}</button>
							${canDel ? `<button class="ttp-action-btn danger btn-card-delete">${__("Delete")}</button>` : ""}
						</div>
					</div>
					<div class="ttp-card-body">
						<div class="ttp-card-title">${frappe.utils.escape_html(t.template_name)}</div>
						<div class="ttp-card-meta" style="margin-bottom:4px;">
							${badge}${defBadge}
							<span style="margin-left:4px;font-size:10px;">
								${__("Page")}: ${t.page_size || "A4"} | ${__("Mode")}: ${t.orientation || "Portrait"}
							</span>
						</div>
						<div class="ttp-card-meta" style="color:#aaa;font-size:10px;">
							${frappe.utils.escape_html(t.modified_by || "")} &nbsp;·&nbsp; ${modDate}
						</div>
					</div>
				</div>`;
		}).join("");

		grid.html(html);
	}

	function build_thumb_svg(t) {
		const land = (t.orientation || "Portrait") === "Landscape";
		const W = land ? 200 : 140, H = land ? 140 : 185;
		const rowH = land ? 9 : 10, rows = land ? 5 : 6;
		const tableY = land ? 62 : 68;

		let rowsHtml = "";
		for (let i = 0; i < rows; i++) {
			const y = tableY + i * rowH;
			rowsHtml += `<rect x="8" y="${y}" width="${W - 16}" height="${rowH - 1}"
				fill="${i % 2 === 0 ? "#fafafa" : "#fff"}" rx="1" stroke="#f0f0f0" stroke-width=".5"/>
				<rect x="8" y="${y}" width="${land ? 70 : 58}" height="${rowH - 1}"
				fill="none" stroke="#f0f0f0" stroke-width=".5"/>`;
		}

		return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg"
			style="width:${W * 0.8}px;height:${H * 0.8}px;filter:drop-shadow(0 2px 6px rgba(0,0,0,.12));">
			<rect width="${W}" height="${H}" fill="white" rx="3" stroke="#e0e0e0" stroke-width="1"/>
			<rect x="0" y="0" width="${W}" height="${land ? 24 : 30}" fill="#c84630" rx="3"/>
			<rect x="0" y="${land ? 20 : 26}" width="${W}" height="4" fill="#c84630"/>
			<circle cx="${land ? 15 : 14}" cy="${land ? 12 : 15}" r="${land ? 8 : 10}" fill="rgba(255,255,255,.22)"/>
			<rect x="${land ? 28 : 30}" y="${land ? 7 : 9}" width="${land ? 85 : 72}" height="5" fill="rgba(255,255,255,.7)" rx="2"/>
			<rect x="${land ? 28 : 30}" y="${land ? 15 : 17}" width="${land ? 55 : 48}" height="3" fill="rgba(255,255,255,.4)" rx="1"/>
			<rect x="8" y="${land ? 32 : 38}" width="${land ? 55 : 50}" height="4" fill="#e8eaed" rx="1"/>
			<rect x="8" y="${land ? 39 : 46}" width="${land ? 40 : 35}" height="3" fill="#f1f3f4" rx="1"/>
			<rect x="8" y="${land ? 45 : 52}" width="${land ? 48 : 42}" height="3" fill="#f1f3f4" rx="1"/>
			<rect x="8" y="${tableY - 8}" width="${W - 16}" height="7" fill="#fce8e6" rx="1"/>
			${rowsHtml}
			<line x1="8" y1="${H - 14}" x2="${W - 8}" y2="${H - 14}" stroke="#e0e0e0" stroke-width=".8"/>
			<rect x="8" y="${H - 11}" width="28" height="3" fill="#e8eaed" rx="1"/>
			<rect x="${W / 2 - 14}" y="${H - 11}" width="28" height="3" fill="#e8eaed" rx="1"/>
			<rect x="${W - 36}" y="${H - 11}" width="28" height="3" fill="#e8eaed" rx="1"/>
		</svg>`;
	}

	// ── Configure view: meta-driven form ──────────────────────────────────────

	/**
	 * Ensure doctype meta is loaded (cached after first call).
	 * Safe to call multiple times; callback is always invoked exactly once.
	 */
	function ensure_meta(callback) {
		if (state.meta) { callback(); return; }
		frappe.model.with_doctype("Transcript Template", function () {
			state.meta = frappe.get_meta("Transcript Template");
			if (!state.meta) {
				frappe.msgprint({
					title: __("Configuration Error"),
					message: __("Could not load Transcript Template field configuration. "
						+ "Please run bench migrate and refresh."),
					indicator: "red",
				});
				return;
			}
			callback();
		});
	}

	function open_configure(name) {
		// Show configure shell with loading indicator while we fetch meta + doc
		show_configure();
		$(wrapper).find("#ttp-cfg-form").html(
			`<div class="ttp-center-msg"><div class="ttp-spinner"></div>${__("Loading…")}</div>`);

		ensure_meta(function () {
			if (name) {
				frappe.call({
					method:  API.get_template,
					args:    { name },
					freeze:  true,
					freeze_message: __("Loading template…"),
					callback(r) {
						if (!r || !r.message) {
							frappe.msgprint({ title: __("Error"), message: __("Could not load template."), indicator: "red" });
							show_list();
							return;
						}
						state.current = r.message;
						render_configure_form(r.message);
						refresh_preview();
					},
					error() {
						frappe.msgprint({ title: __("Error"), message: __("Could not load template. Please try again."), indicator: "red" });
						show_list();
					},
				});
			} else {
				state.current = {
					template_type: "Custom",
					page_size:     "A4",
					orientation:   "Portrait",
					is_default:    0,
				};
				render_configure_form(state.current);
				refresh_preview();
			}
		});
	}

	/**
	 * Build the configure form entirely from the doctype meta.
	 * Groups fields into sections (Section Break = accordion).
	 * Fields before the first Section Break appear in a top "base" card.
	 * Any new field added to the doctype automatically appears here.
	 */
	function render_configure_form(doc) {
		state.field_controls = {};
		const form = $(wrapper).find("#ttp-cfg-form").empty();

		// Update header title
		$(wrapper).find("#ttp-cfg-title").text(
			doc.name
				? __("Configure: {0}", [doc.template_name || doc.name])
				: __("New Template")
		);
		// Update Set Default button
		$(wrapper).find("#ttp-cfg-set-default")
			.css({ "border-color": doc.is_default ? "#1e7e34" : "", color: doc.is_default ? "#1e7e34" : "" })
			.text(doc.is_default ? __("✓ Default") : __("Set as Default"));

		const fields = (state.meta.fields || []).filter(
			f => !f.hidden && f.fieldtype !== "Tab Break"
		);

		// Split into [base_fields, ...sections]
		const { base, sections } = group_by_sections(fields);

		// ── Base card (fields before first section) ──────────────────────
		if (base.length) {
			const base_card = $(`<div class="ttp-base-card"></div>`);
			const base_grid = $(`<div class="ttp-base-grid"></div>`);

			// base is [[col1_fields], [col2_fields], ...] — iterate columns, then fields
			base.forEach(col_fields => {
				col_fields.forEach(f => {
					const wrap = $(`<div class="ttp-field-wrap"></div>`);
					const ctrl = make_field_control(f, doc);
					wrap.append(ctrl.$el);
					base_grid.append(wrap);
				});
			});

			base_card.append(base_grid);
			form.append(base_card);
		}

		// ── Section accordions ────────────────────────────────────────────
		sections.forEach((sec, idx) => {
			const acc_body = $(`<div class="ttp-acc-body ${idx === 0 ? "open" : ""}"></div>`);
			const icon     = SECTION_ICON[sec.label] || SECTION_ICON._default;

			const acc = $(`
				<div class="ttp-accordion">
					<div class="ttp-acc-header">
						<div class="ttp-acc-icon">
							${icon}
							<span class="ttp-acc-title">${frappe.utils.escape_html(sec.label || "")}</span>
						</div>
						<span class="ttp-acc-chevron ${idx === 0 ? "open" : ""}">
							<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
								fill="none" stroke="currentColor" stroke-width="2.5"
								stroke-linecap="round" stroke-linejoin="round">
								<polyline points="6 9 12 15 18 9"/>
							</svg>
						</span>
					</div>
				</div>`);

			// Render column groups inside the section
			if (sec.columns.length > 1) {
				const cols_row = $(`<div class="ttp-cols"></div>`);
				sec.columns.forEach(col_fields => {
					const col = $(`<div class="ttp-col"></div>`);
					col_fields.forEach(f => {
						const wrap = $(`<div class="ttp-field-wrap"></div>`);
						wrap.append(make_field_control(f, doc).$el);
						col.append(wrap);
					});
					cols_row.append(col);
				});
				acc_body.append(cols_row);
			} else {
				(sec.columns[0] || []).forEach(f => {
					const wrap = $(`<div class="ttp-field-wrap"></div>`);
					wrap.append(make_field_control(f, doc).$el);
					acc_body.append(wrap);
				});
			}

			acc.append(acc_body);
			form.append(acc);
		});
	}

	/**
	 * Split a flat fields array into:
	 *   base     – array of column-groups before the first Section Break
	 *   sections – array of { label, columns: [[fields...], ...] }
	 */
	function group_by_sections(fields) {
		const base_columns  = [[]];   // columns before first section
		const sections      = [];
		let   in_base       = true;
		let   current_sec   = null;

		for (const f of fields) {
			if (f.fieldtype === "Section Break") {
				in_base     = false;
				current_sec = { label: f.label || "", columns: [[]] };
				sections.push(current_sec);
			} else if (f.fieldtype === "Column Break") {
				if (in_base) {
					base_columns.push([]);
				} else if (current_sec) {
					current_sec.columns.push([]);
				}
			} else {
				if (in_base) {
					base_columns[base_columns.length - 1].push(f);
				} else if (current_sec) {
					current_sec.columns[current_sec.columns.length - 1].push(f);
				}
			}
		}

		// Remove empty trailing columns
		const clean_base = base_columns.filter(c => c.length);

		// Return base as a flat array of column-arrays, e.g. [[f1,f2], [f3,f4]]
		return { base: clean_base, sections };
	}

	// ── Field control factory ─────────────────────────────────────────────────

	/**
	 * Create the appropriate HTML control for a field.
	 * Returns { $el: jQuery, get_value(), set_value(v) }
	 * Also registers in state.field_controls[fieldname].
	 */
	function make_field_control(f, doc) {
		const value = (doc && doc[f.fieldname] !== undefined && doc[f.fieldname] !== null)
			? doc[f.fieldname]
			: (f.default !== undefined ? f.default : "");

		let ctrl;
		switch (f.fieldtype) {
			case "Attach Image":
			case "Attach":
				ctrl = make_attach_control(f, value);
				break;
			case "Check":
				ctrl = make_check_control(f, value);
				break;
			case "Select":
				ctrl = make_select_control(f, value);
				break;
			case "Int":
			case "Float":
				ctrl = make_number_control(f, value);
				break;
			case "Small Text":
			case "Text":
				ctrl = make_textarea_control(f, value);
				break;
			default:
				ctrl = make_text_control(f, value);
		}

		// Register in field_controls map
		state.field_controls[f.fieldname] = ctrl;

		// Wire live-preview refresh for non-attach fields
		if (!["Attach Image", "Attach"].includes(f.fieldtype)) {
			ctrl.$el.on("input change", () => schedule_preview_refresh());
		}

		return ctrl;
	}

	function label_html(f) {
		const reqd = f.reqd ? `<span class="reqd">*</span>` : "";
		return `<label class="ttp-label">${frappe.utils.escape_html(__(f.label || f.fieldname))}${reqd}</label>
		        ${f.description ? `<div class="ttp-desc">${frappe.utils.escape_html(__(f.description))}</div>` : ""}`;
	}

	// ── Specific control builders ─────────────────────────────────────────────

	function make_text_control(f, value) {
		const $wrap  = $(`<div></div>`).html(label_html(f));
		const $input = $(`<input type="text" class="ttp-control" placeholder="${frappe.utils.escape_html(f.placeholder || "")}"
			${f.read_only ? "disabled" : ""}/>`)
			.val(value || "");
		$wrap.append($input);
		return {
			$el: $wrap,
			get_value: () => $input.val(),
			set_value: v  => $input.val(v || ""),
		};
	}

	function make_textarea_control(f, value) {
		const $wrap     = $(`<div></div>`).html(label_html(f));
		const $textarea = $(`<textarea class="ttp-control" rows="3"
			placeholder="${frappe.utils.escape_html(f.placeholder || "")}"
			${f.read_only ? "disabled" : ""}></textarea>`)
			.val(value || "");
		$wrap.append($textarea);
		return {
			$el: $wrap,
			get_value: () => $textarea.val(),
			set_value: v  => $textarea.val(v || ""),
		};
	}

	function make_number_control(f, value) {
		const $wrap  = $(`<div></div>`).html(label_html(f));
		const $input = $(`<input type="number" class="ttp-control"
			min="${f.non_negative ? 0 : ""}" step="${f.fieldtype === "Float" ? "any" : 1}"
			${f.read_only ? "disabled" : ""}/>`)
			.val(value !== "" ? value : (f.default || ""));
		$wrap.append($input);
		return {
			$el: $wrap,
			get_value: () => { const v = $input.val(); return v === "" ? null : Number(v); },
			set_value: v  => $input.val(v !== null && v !== undefined ? v : ""),
		};
	}

	function make_select_control(f, value) {
		const $wrap   = $(`<div></div>`).html(label_html(f));
		const options = (f.options || "").split("\n").filter(Boolean);
		const $select = $(`<select class="ttp-control" ${f.read_only ? "disabled" : ""}></select>`);
		if (!f.reqd) $select.append(`<option value=""></option>`);
		options.forEach(opt => {
			$select.append(`<option value="${frappe.utils.escape_html(opt)}">${frappe.utils.escape_html(__(opt))}</option>`);
		});
		$select.val(value || "");
		$wrap.append($select);
		return {
			$el: $wrap,
			get_value: () => $select.val(),
			set_value: v  => $select.val(v || ""),
		};
	}

	function make_check_control(f, value) {
		const checked  = value == 1 || value === true || value === "1";
		const uid      = `ttp-chk-${f.fieldname}-${Date.now()}`;

		const $wrap    = $(`<div style="padding-top:2px;"></div>`);
		const $label   = $(`<label class="ttp-toggle-wrap" for="${uid}"></label>`);
		const $toggle  = $(`<span class="ttp-toggle"><input type="checkbox" id="${uid}" ${checked ? "checked" : ""}/>
			<span class="ttp-slider"></span></span>`);
		const $text    = $(`<span class="ttp-toggle-label">${frappe.utils.escape_html(__(f.label || f.fieldname))}</span>`);
		$label.append($toggle, $text);
		$wrap.append($label);

		const $input = $toggle.find("input");
		return {
			$el: $wrap,
			get_value: () => $input.is(":checked") ? 1 : 0,
			set_value: v  => $input.prop("checked", v == 1 || v === true),
		};
	}

	/**
	 * Attach Image control that uses frappe.ui.FileUploader (works local + cloud).
	 * Falls back gracefully if the uploader is unavailable.
	 */
	function make_attach_control(f, value) {
		const $wrap        = $(`<div></div>`).html(label_html(f));
		const $img         = $(`<img style="max-height:60px;max-width:160px;object-fit:contain;border-radius:4px;"/>`);
		const $placeholder = $(`
			<div class="ttp-attach-placeholder">
				<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24"
					fill="none" stroke="#ccc" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
					<rect x="3" y="3" width="18" height="18" rx="2"/>
					<circle cx="8.5" cy="8.5" r="1.5"/>
					<polyline points="21 15 16 10 5 21"/>
				</svg>
				<span style="font-size:11px;color:#bbb;margin-top:4px;">${__("Click to upload")}</span>
			</div>`);
		const $remove      = $(`<button type="button" class="ttp-attach-remove" title="${__("Remove")}">✕</button>`);
		const $widget      = $(`<div class="ttp-attach-widget" title="${__("Click to upload image")}"></div>`)
			.append($img, $placeholder, $remove);

		const $upload_btn  = $(`<button type="button" class="ttp-btn-upload">${__("Upload")}</button>`);
		const $clear_btn   = $(`<button type="button" class="ttp-btn-clear">${__("Clear")}</button>`);
		const $actions     = $(`<div class="ttp-attach-actions"></div>`).append($upload_btn, $clear_btn);

		$wrap.append($widget, $actions);

		let current_value = "";

		function set_value(v) {
			current_value = v || "";
			if (current_value) {
				$img.attr("src", current_value).show();
				$placeholder.hide();
				$remove.show();
			} else {
				$img.hide().attr("src", "");
				$placeholder.show();
				$remove.hide();
			}
		}

		function do_upload() {
			// Guard: frappe.ui.FileUploader must exist (Frappe v14+)
			if (typeof frappe.ui.FileUploader !== "function") {
				frappe.msgprint({ title: __("Not Supported"), message: __("File upload requires Frappe v14 or later."), indicator: "orange" });
				return;
			}
			try {
				new frappe.ui.FileUploader({
					restrictions: {
						allowed_file_types: ["image/*"],
						max_number_of_files: 1,
					},
					allow_multiple: false,
					on_success(file_doc) {
						if (file_doc && file_doc.file_url) {
							set_value(file_doc.file_url);
							schedule_preview_refresh();
						}
					},
				});
			} catch (err) {
				frappe.show_alert({ message: __("File upload failed. Check console for details."), indicator: "red" }, 5);
				console.error("[TranscriptTemplate] FileUploader error:", err);
			}
		}

		function do_clear() {
			set_value("");
			schedule_preview_refresh();
		}

		// Click on widget background = upload
		$widget.on("click", function (e) {
			if ($(e.target).is("button")) return;
			do_upload();
		});
		$upload_btn.on("click", do_upload);
		$clear_btn.on("click", do_clear);
		$remove.on("click", do_clear);

		// Set initial value
		set_value(value);

		return {
			$el: $wrap,
			get_value: () => current_value,
			set_value,
		};
	}

	// ── Form data helpers ─────────────────────────────────────────────────────

	function collect_form_values() {
		const values = {};
		Object.entries(state.field_controls).forEach(([fieldname, ctrl]) => {
			values[fieldname] = ctrl.get_value();
		});
		// Carry over the doc name when editing an existing template
		if (state.current && state.current.name) {
			values.name = state.current.name;
		}
		return values;
	}

	// ── Preview ───────────────────────────────────────────────────────────────

	function schedule_preview_refresh() {
		clearTimeout(state._preview_timer);
		state._preview_timer = setTimeout(refresh_preview, 280);
	}

	function get_val(fieldname) {
		const ctrl = state.field_controls[fieldname];
		if (ctrl) return ctrl.get_value();
		return state.current ? state.current[fieldname] : "";
	}

	/**
	 * Dynamically collect non-empty values of all displayable fields that
	 * belong to a given section (identified by its Section Break label).
	 * Field types excluded from display: Section Break, Column Break, Check,
	 * Attach, Attach Image, HTML, Fold, Tab Break.
	 *
	 * This means any field added to (e.g.) the "Institute Address" section in
	 * the Transcript Template doctype will automatically appear in the preview
	 * without any code change — the meta is always read fresh from the cache.
	 */
	function collect_section_display_values(section_label) {
		const SKIP_TYPES = new Set([
			"Section Break", "Column Break", "Check",
			"Attach", "Attach Image", "HTML", "Fold", "Tab Break",
		]);

		if (!state.meta || !state.meta.fields) {
			return [];
		}

		let in_section = false;
		const parts = [];

		for (const f of state.meta.fields) {
			if (f.fieldtype === "Section Break") {
				if (in_section) break;          // left the target section
				in_section = (f.label === section_label);
				continue;
			}
			if (!in_section) continue;
			if (f.hidden || SKIP_TYPES.has(f.fieldtype)) continue;

			const raw = get_val(f.fieldname);
			// Skip the "Show …" toggles and empty values
			if (raw === null || raw === undefined || String(raw).trim() === "") continue;
			parts.push(String(raw).trim());
		}

		return parts;
	}

	function refresh_preview() {
		const land   = (get_val("orientation") || "Portrait") === "Landscape";
		const pw     = land ? "100%" : "74%";
		const ratio  = land ? "70.7%" : "141.4%";

		const logo_src = get_val("show_institute_logo") ? get_val("institute_logo") : "";
		const logoHtml = logo_src
			? `<img src="${frappe.utils.escape_html(logo_src)}"
			       style="max-height:${Math.max(30, Math.min(60, parseInt(get_val("logo_width")) * 0.38 || 42))}px;
			              max-width:140px;object-fit:contain;"/>`
			: `<div style="width:38px;height:38px;background:rgba(255,255,255,.22);border-radius:50%;display:inline-block;"></div>`;

		const instName    = frappe.utils.escape_html(get_val("institute_name") || __("Institute Name"));
		const headTitle   = frappe.utils.escape_html(get_val("header_title") || __("OFFICIAL TRANSCRIPT OF ACADEMIC RECORDS"));
		const showAddr    = get_val("show_institute_address");

		// Dynamically build address from ALL text fields in "Institute Address"
		// section — new fields (e.g. Pincode) appear automatically.
		const addrParts   = collect_section_display_values("Institute Address");
		const instAddr    = (showAddr && addrParts.length)
			? frappe.utils.escape_html(addrParts.join(", ")) : "";

		const alignment   = (get_val("logo_alignment") || "Center").toLowerCase();

		// Signatures
		const sigHtml = [1, 2, 3].map(n => {
			const lbl = frappe.utils.escape_html(get_val(`sig_label_${n}`) || "");
			const img = get_val(`sig_image_${n}`);
			if (!lbl && !img) return "";
			const imgEl = img
				? `<img src="${frappe.utils.escape_html(img)}" style="height:18px;margin-bottom:2px;display:block;"/>`
				: `<div style="width:50px;height:16px;border-bottom:1px solid #999;margin-bottom:2px;"></div>`;
			return `<div style="text-align:center;">${imgEl}<span style="font-size:9px;color:#555;">${lbl}</span></div>`;
		}).filter(Boolean).join("");

		// Watermark
		const showWm = get_val("show_watermark");
		const wmText = get_val("watermark_text");
		const wmLogo = get_val("watermark_logo");
		const wmOp   = (parseInt(get_val("watermark_opacity")) || 15) / 100;
		let watermarkHtml = "";
		if (showWm) {
			if (wmLogo) {
				watermarkHtml = `<img src="${frappe.utils.escape_html(wmLogo)}" style="position:absolute;top:50%;left:50%;
					transform:translate(-50%,-50%);opacity:${wmOp};max-width:60%;max-height:60%;
					pointer-events:none;z-index:0;"/>`;
			} else if (wmText) {
				watermarkHtml = `<div style="position:absolute;top:50%;left:50%;
					transform:translate(-50%,-50%) rotate(-30deg);opacity:${wmOp};
					font-size:28px;font-weight:900;color:#c84630;white-space:nowrap;
					pointer-events:none;z-index:0;letter-spacing:2px;">
					${frappe.utils.escape_html(wmText)}</div>`;
			}
		}

		// Course rows
		const courseRows = [1, 2, 3, 4].map((_, i) =>
			`<tr style="background:${i % 2 === 0 ? "#fafafa" : "#fff"}">
				<td style="padding:3px 6px;border:1px solid #eee;font-size:9px;color:#555;">Sample Course ${i + 1}</td>
				${get_val("show_credits") ? `<td style="padding:3px 6px;border:1px solid #eee;font-size:9px;text-align:center;">${3 + i}</td>` : ""}
				<td style="padding:3px 6px;border:1px solid #eee;font-size:9px;text-align:center;">A</td>
				<td style="padding:3px 6px;border:1px solid #eee;font-size:9px;text-align:center;">9.0</td>
			</tr>`
		).join("");

		$(wrapper).find("#ttp-preview-content").html(`
			<div style="width:${pw};margin:0 auto;position:relative;font-family:Georgia,serif;">
				<div style="padding-top:${ratio};position:relative;">
					<div style="position:absolute;inset:0;background:white;
					            border:1px solid #ddd;border-radius:3px;overflow:hidden;
					            box-shadow:0 2px 10px rgba(0,0,0,.1);">
						${watermarkHtml}
						<!-- Header -->
						<div style="background:#c84630;padding:${land ? "8px 12px" : "10px 14px"};
						            display:flex;align-items:center;gap:10px;">
							<div style="text-align:${alignment};flex-shrink:0;">${logoHtml}</div>
							<div style="flex:1;">
								<div style="font-size:${land ? "10px" : "11px"};font-weight:700;color:white;letter-spacing:.5px;">${instName}</div>
								<div style="font-size:${land ? "8px" : "9px"};color:rgba(255,255,255,.85);margin-top:1px;">${headTitle}</div>
								${instAddr ? `<div style="font-size:8px;color:rgba(255,255,255,.6);margin-top:1px;">${instAddr}</div>` : ""}
							</div>
						</div>
						<!-- Student row -->
						<div style="padding:${land ? "6px 10px" : "8px 12px"};display:flex;gap:8px;border-bottom:1px solid #f0f0f0;align-items:flex-start;">
							${get_val("show_student_photo") ? `<div style="width:30px;height:36px;background:#e8eaed;border-radius:2px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:8px;color:#aaa;">Photo</div>` : ""}
							<div style="flex:1;">
								<div style="font-size:11px;font-weight:700;color:#222;">${__("Student Name Here")}</div>
								${get_val("show_registration_id") ? `<div style="font-size:9px;color:#777;">${__("Reg. ID")}: REG2024001</div>` : ""}
								<div style="font-size:9px;color:#777;">${__("Programme")}: B.A. LL.B (Hons.)</div>
							</div>
							${get_val("show_cgpa") ? `<div><div style="font-size:8px;color:#888;">CGPA</div><div style="font-size:16px;font-weight:700;color:#c84630;">8.52</div></div>` : ""}
						</div>
						<!-- Courses -->
						<div style="padding:${land ? "5px 10px" : "6px 12px"};">
							${get_val("show_semester_wise") ? `<div style="font-size:9px;font-weight:700;color:#c84630;margin-bottom:4px;">${__("SEMESTER I")}</div>` : ""}
							<table style="width:100%;border-collapse:collapse;">
								<thead>
									<tr style="background:#fce8e6;">
										<th style="padding:3px 6px;text-align:left;border:1px solid #eee;font-size:9px;">${__("Course")}</th>
										${get_val("show_credits") ? `<th style="padding:3px 6px;border:1px solid #eee;font-size:9px;">${__("Cr")}</th>` : ""}
										<th style="padding:3px 6px;border:1px solid #eee;font-size:9px;">${__("Grade")}</th>
										<th style="padding:3px 6px;border:1px solid #eee;font-size:9px;">${__("GP")}</th>
									</tr>
								</thead>
								<tbody>${courseRows}</tbody>
							</table>
						</div>
						<!-- Signatures -->
						${sigHtml ? `<div style="position:absolute;bottom:6px;left:12px;right:12px;
							display:flex;justify-content:space-around;">${sigHtml}</div>` : ""}
					</div>
				</div>
			</div>`);
	}

	// ── Actions ───────────────────────────────────────────────────────────────

	function do_save() {
		const data = collect_form_values();

		if (!data.template_name || !String(data.template_name).trim()) {
			frappe.show_alert({ message: __("Template Name is required."), indicator: "red" }, 4);
			const ctrl = state.field_controls["template_name"];
			if (ctrl) ctrl.$el.find("input").focus();
			return;
		}

		const $btn = $(wrapper).find("#ttp-cfg-save").prop("disabled", true).text(__("Saving…"));

		frappe.call({
			method:  API.save_template,
			args:    { data: JSON.stringify(data) },
			callback(r) {
				$btn.prop("disabled", false).text(__("Save"));
				if (!r || !r.message) return;
				state.current = r.message;
				$(wrapper).find("#ttp-cfg-title").text(__("Configure: {0}", [r.message.template_name]));
				frappe.show_alert({ message: __("Template '{0}' saved.", [r.message.template_name]), indicator: "green" }, 4);
			},
			error(r) {
				$btn.prop("disabled", false).text(__("Save"));
				const msg = r && r.message ? r.message : __("Save failed. Please try again.");
				frappe.msgprint({ title: __("Save Error"), message: msg, indicator: "red" });
			},
		});
	}

	function handle_set_default() {
		if (!state.current || !state.current.name) {
			frappe.msgprint(__("Please save the template first, then set it as default."));
			return;
		}
		frappe.call({
			method: API.set_default,
			args:   { name: state.current.name },
			callback(r) {
				if (r && r.message && r.message.success) {
					state.current.is_default = 1;
					$(wrapper).find("#ttp-cfg-set-default")
						.css({ "border-color": "#1e7e34", color: "#1e7e34" })
						.text(__("✓ Default"));
					frappe.show_alert({ message: __("Default template updated."), indicator: "green" }, 3);
				}
			},
		});
	}

	// ── Initial page load ──────────────────────────────────────────────────────
	// Seed built-in templates once (idempotent), then show the list.
	frappe.call({
		method:  API.seed_default_templates,
		callback() { load_templates(); },
		error()   { load_templates(); },   // still load even if seeding fails
	});
};
