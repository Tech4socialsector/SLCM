/* =====================================================
   Examination Planner - Main SPA
   ===================================================== */

frappe.pages['examination-planner'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Examination Planner',
		single_column: true
	});

	// Inject CSS
	if (!document.getElementById('ep-styles')) {
		var link = document.createElement('link');
		link.id = 'ep-styles';
		link.rel = 'stylesheet';
		link.href = '/assets/slcm/css/examination_planner.css';
		document.head.appendChild(link);
	}

	new ExaminationPlanner(page);
};

class ExaminationPlanner {
	constructor(page) {
		this.page = page;
		this.current_tab = 'exams';
		this._terms = null;
		this._components = null;
		this._assessment_types = null;
		this._schema_state = {}; // current schema being edited
		this.setup();
	}

	setup() {
		this.render_main();
		this.switch_tab('exams');
	}

	// ── Main Layout ──────────────────────────────────────
	render_main() {
		this.page.main.html(`
			<div class="ep-container">
				<div class="ep-tabs" id="ep-tabs"></div>
				<div class="ep-tab-content" id="ep-tab-content">
					<div class="ep-loading">Loading</div>
				</div>
			</div>
		`);
		this._render_tab_nav();
	}

	_render_tab_nav() {
		const tabs = [
			{ key: 'exams', label: 'Exams' },
			{ key: 'components', label: 'Components' },
			{ key: 'types', label: 'Types' },
			{ key: 'schemas', label: 'Schemas' },
			{ key: 'settings', label: 'Settings' },
			{ key: 'moderation', label: 'Moderation Policy' },
			{ key: 'seating', label: 'Seating Plan' },
			{ key: 'division', label: 'Division Setting' },
		];
		const $tabs = $('#ep-tabs');
		$tabs.empty();
		tabs.forEach(tab => {
			$tabs.append(
				`<a class="ep-tab ${tab.key === this.current_tab ? 'active' : ''}"
					data-tab="${tab.key}">${tab.label}</a>`
			);
		});
		$tabs.on('click', '.ep-tab', (e) => {
			const tab = $(e.currentTarget).data('tab');
			this.switch_tab(tab);
		});
	}

	switch_tab(tab) {
		this.current_tab = tab;
		$('.ep-tab').removeClass('active');
		$(`.ep-tab[data-tab="${tab}"]`).addClass('active');
		switch (tab) {
			case 'exams': this.load_exams(); break;
			case 'components': this.load_components(); break;
			case 'types': this.load_types(); break;
			case 'schemas': this.load_schemas(); break;
			default: this._placeholder_tab(tab); break;
		}
	}

	_placeholder_tab(tab) {
		$('#ep-tab-content').html(`
			<div class="ep-empty" style="padding:80px 20px;">
				<div style="font-size:40px;margin-bottom:12px;">🚧</div>
				<div style="font-size:15px;color:#888;">${__('This section is coming soon.')}</div>
			</div>
		`);
	}

	// ── Utility ──────────────────────────────────────────
	_badge_class(type) {
		if (!type) return 'ep-badge-custom';
		const t = type.toLowerCase();
		if (t.includes('re exam') || t.includes('reexam')) return 'ep-badge-reexam';
		if (t.includes('makeup')) return 'ep-badge-makeup';
		if (t.includes('default')) return 'ep-badge-default';
		if (t.includes('reexam/makeup')) return 'ep-badge-reexam-makeup';
		return 'ep-badge-custom';
	}

	_badge_label(type) {
		if (!type) return 'Custom';
		const map = {
			'Custom': 'Custom',
			'Re Exam': 'Re Exam',
			'Makeup': 'Makeup',
			'Default Assessment': 'Default Assessment',
			'Assessment': 'Assessment',
			'ReExam/Makeup Assessment': 'ReExam/Makup',
		};
		return map[type] || type;
	}

	// ── EXAMS TAB ────────────────────────────────────────
	load_exams(search = '') {
		$('#ep-tab-content').html(this._toolbar('Search by Exam or Term Name', 'Create New Plan', 'show_create_exam_dialog'));
		$('#ep-tab-content').append('<div id="ep-content-area"></div>');
		this._fetch_exams(search);

		$('#ep-tab-content').on('input', '.ep-search', (e) => {
			clearTimeout(this._exam_search_timer);
			this._exam_search_timer = setTimeout(() => this._fetch_exams(e.target.value), 300);
		});
		$('#ep-tab-content').on('click', '.ep-btn-primary', () => this.show_create_exam_dialog());
	}

	_fetch_exams(search) {
		$('#ep-content-area').html('<div class="ep-loading">Loading</div>');
		frappe.call({
			method: 'slcm.slcm.page.examination_planner.examination_planner.get_exam_plans',
			args: { search: search || '' },
			callback: (r) => {
				const data = r.message || [];
				if (!data.length) {
					$('#ep-content-area').html('<div class="ep-empty">No exam plans found.</div>');
					return;
				}
				let rows = data.map(d => `
					<tr>
						<td class="link-cell">
							<a href="#" class="ep-exam-link" data-name="${d.name}">${d.exam_name}</a>
							<span class="ep-edit-icon" data-name="${d.name}" data-exam="${d.exam_name}" data-term="${d.term || ''}">
								<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
									<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
								</svg>
							</span>
						</td>
						<td>${d.term || ''}</td>
					</tr>
				`).join('');
				$('#ep-content-area').html(`
					<table class="ep-list-table">
						<thead>
							<tr>
								<th>Exam Name</th>
								<th>Term</th>
							</tr>
						</thead>
						<tbody>${rows}</tbody>
					</table>
				`);
			}
		});
	}

	show_create_exam_dialog(data = {}) {
		this._ensure_terms(() => {
			const is_edit = !!data.name;
			const title = is_edit ? 'Edit Exam Plan' : 'Create New Plan';
			const term_options = (this._terms || []).map(t =>
				`<option value="${t.name}" ${data.term === t.name ? 'selected' : ''}>${t.term_name}</option>`
			).join('');
			const html = `
				<div class="ep-dialog-overlay" id="ep-exam-dialog">
					<div class="ep-dialog">
						<div class="ep-dialog-header">${__(title)}</div>
						<div class="ep-dialog-body">
							<div class="ep-form-group" style="margin-bottom:14px;">
								<label>${__('Examination Name')}</label>
								<input type="text" id="ep-exam-name" value="${data.exam_name || ''}" placeholder="Enter Examination Name"/>
							</div>
							<div class="ep-form-group">
								<label>${__('Term')}</label>
								<select id="ep-exam-term">
									<option value="">Select Term</option>
									${term_options}
								</select>
							</div>
						</div>
						<div class="ep-dialog-footer">
							<button class="ep-btn-cancel" id="ep-exam-cancel">Cancel</button>
							<button class="ep-btn-save" id="ep-exam-create">${is_edit ? 'Save' : 'Create'}</button>
						</div>
					</div>
				</div>
			`;
			$('body').append(html);

			$('#ep-exam-cancel').on('click', () => $('#ep-exam-dialog').remove());
			$('#ep-exam-dialog').on('click', (e) => { if ($(e.target).is('#ep-exam-dialog')) $('#ep-exam-dialog').remove(); });

			$('#ep-exam-create').on('click', () => {
				const exam_name = $('#ep-exam-name').val().trim();
				const term = $('#ep-exam-term').val();
				if (!exam_name) {
					frappe.msgprint(__('Please enter an examination name.'));
					return;
				}
				frappe.call({
					method: 'slcm.slcm.page.examination_planner.examination_planner.create_exam_plan',
					args: { exam_name, term },
					freeze: true,
					callback: (r) => {
						$('#ep-exam-dialog').remove();
						frappe.show_alert({ message: __('Exam plan created successfully.'), indicator: 'green' });
						this._fetch_exams('');
					},
					error: (r) => {
						frappe.msgprint(r.message || __('Failed to create exam plan.'));
					}
				});
			});
		});
	}

	_ensure_terms(callback) {
		if (this._terms) { callback(); return; }
		frappe.call({
			method: 'slcm.slcm.page.examination_planner.examination_planner.get_terms',
			callback: (r) => {
				this._terms = r.message || [];
				callback();
			}
		});
	}

	// ── COMPONENTS TAB ──────────────────────────────────
	load_components(search = '') {
		$('#ep-tab-content').html(this._toolbar('Search by Exam Component Name', 'Add New Component', 'show_component_dialog'));
		$('#ep-tab-content').append('<div id="ep-content-area"></div>');
		this._fetch_components(search);

		$('#ep-tab-content').on('input', '.ep-search', (e) => {
			clearTimeout(this._comp_search_timer);
			this._comp_search_timer = setTimeout(() => this._fetch_components(e.target.value), 300);
		});
		$('#ep-tab-content').on('click', '.ep-btn-primary', () => this.show_component_dialog());
		$('#ep-tab-content').on('click', '.ep-edit-icon', (e) => {
			const $el = $(e.currentTarget);
			this.show_component_dialog({
				name: $el.data('name'),
				component_name: $el.data('component'),
				component_type: $el.data('type')
			});
		});
	}

	_fetch_components(search) {
		$('#ep-content-area').html('<div class="ep-loading">Loading</div>');
		frappe.call({
			method: 'slcm.slcm.page.examination_planner.examination_planner.get_components',
			args: { search: search || '' },
			callback: (r) => {
				const data = r.message || [];
				if (!data.length) {
					$('#ep-content-area').html('<div class="ep-empty">No components found.</div>');
					return;
				}
				let rows = data.map(d => `
					<tr>
						<td>
							${d.component_name}
							<span class="ep-edit-icon" data-name="${d.name}" data-component="${d.component_name}" data-type="${d.component_type}">
								<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
									<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
								</svg>
							</span>
						</td>
						<td>
							<span class="ep-badge ${this._badge_class(d.component_type)}">
								${this._badge_label(d.component_type)}
							</span>
						</td>
					</tr>
				`).join('');
				$('#ep-content-area').html(`
					<table class="ep-list-table">
						<thead><tr><th>Name</th><th>Type</th></tr></thead>
						<tbody>${rows}</tbody>
					</table>
				`);
			}
		});
	}

	show_component_dialog(data = {}) {
		const is_edit = !!data.name;
		const types = ['Custom', 'Re Exam', 'Makeup'];
		const type_options = types.map(t =>
			`<option value="${t}" ${data.component_type === t ? 'selected' : ''}>${t}</option>`
		).join('');
		const html = `
			<div class="ep-dialog-overlay" id="ep-comp-dialog">
				<div class="ep-dialog">
					<div class="ep-dialog-header">${is_edit ? __('Edit Component') : __('Add New Component')}</div>
					<div class="ep-dialog-body">
						<div class="ep-form-group" style="margin-bottom:14px;">
							<label>${__('Component Name')}</label>
							<input type="text" id="ep-comp-name" value="${data.component_name || ''}" placeholder="Enter Component Name"/>
						</div>
						<div class="ep-form-group">
							<label>${__('Component Type')}</label>
							<select id="ep-comp-type">
								${type_options}
							</select>
						</div>
					</div>
					<div class="ep-dialog-footer">
						<button class="ep-btn-cancel" id="ep-comp-cancel">Cancel</button>
						<button class="ep-btn-save" id="ep-comp-save">${is_edit ? 'Save' : 'Add'}</button>
					</div>
				</div>
			</div>
		`;
		$('body').append(html);

		$('#ep-comp-cancel').on('click', () => $('#ep-comp-dialog').remove());
		$('#ep-comp-dialog').on('click', (e) => { if ($(e.target).is('#ep-comp-dialog')) $('#ep-comp-dialog').remove(); });

		$('#ep-comp-save').on('click', () => {
			const component_name = $('#ep-comp-name').val().trim();
			const component_type = $('#ep-comp-type').val();
			if (!component_name) { frappe.msgprint(__('Please enter a component name.')); return; }
			frappe.call({
				method: 'slcm.slcm.page.examination_planner.examination_planner.save_component',
				args: { component_name, component_type, name: data.name || null },
				freeze: true,
				callback: (r) => {
					$('#ep-comp-dialog').remove();
					frappe.show_alert({ message: __('Component saved.'), indicator: 'green' });
					this._components = null;
					this._fetch_components('');
				}
			});
		});
	}

	// ── TYPES TAB ────────────────────────────────────────
	load_types(search = '') {
		$('#ep-tab-content').html(this._toolbar('Search by Exam Type Name', 'Add New Exam Type', 'show_type_dialog'));
		$('#ep-tab-content').append('<div id="ep-content-area"></div>');
		this._fetch_types(search);

		$('#ep-tab-content').on('input', '.ep-search', (e) => {
			clearTimeout(this._type_search_timer);
			this._type_search_timer = setTimeout(() => this._fetch_types(e.target.value), 300);
		});
		$('#ep-tab-content').on('click', '.ep-btn-primary', () => this.show_type_dialog());
		$('#ep-tab-content').on('click', '.ep-edit-icon', (e) => {
			const $el = $(e.currentTarget);
			this.show_type_dialog({
				name: $el.data('name'),
				type_name: $el.data('typename'),
				assessment_type: $el.data('atype')
			});
		});
	}

	_fetch_types(search) {
		$('#ep-content-area').html('<div class="ep-loading">Loading</div>');
		frappe.call({
			method: 'slcm.slcm.page.examination_planner.examination_planner.get_assessment_types',
			args: { search: search || '' },
			callback: (r) => {
				const data = r.message || [];
				if (!data.length) {
					$('#ep-content-area').html('<div class="ep-empty">No assessment types found.</div>');
					return;
				}
				let rows = data.map(d => `
					<tr>
						<td>
							${d.type_name}
							<span class="ep-edit-icon" data-name="${d.name}" data-typename="${d.type_name}" data-atype="${d.assessment_type}">
								<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
									<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
								</svg>
							</span>
						</td>
						<td>
							<span class="ep-badge ${this._badge_class(d.assessment_type)}">
								${this._badge_label(d.assessment_type)}
							</span>
						</td>
					</tr>
				`).join('');
				$('#ep-content-area').html(`
					<table class="ep-list-table">
						<thead><tr><th>Name</th><th>Type</th></tr></thead>
						<tbody>${rows}</tbody>
					</table>
				`);
			}
		});
	}

	show_type_dialog(data = {}) {
		const is_edit = !!data.name;
		const types = ['Default Assessment', 'Assessment', 'ReExam/Makeup Assessment'];
		const type_options = types.map(t =>
			`<option value="${t}" ${data.assessment_type === t ? 'selected' : ''}>${t}</option>`
		).join('');
		const html = `
			<div class="ep-dialog-overlay" id="ep-type-dialog">
				<div class="ep-dialog">
					<div class="ep-dialog-header">${is_edit ? __('Edit Exam Type') : __('Add New Exam Type')}</div>
					<div class="ep-dialog-body">
						<div class="ep-form-group" style="margin-bottom:14px;">
							<label>${__('Type Name')}</label>
							<input type="text" id="ep-type-name" value="${data.type_name || ''}" placeholder="Enter Type Name"/>
						</div>
						<div class="ep-form-group">
							<label>${__('Assessment Type')}</label>
							<select id="ep-type-atype">
								${type_options}
							</select>
						</div>
					</div>
					<div class="ep-dialog-footer">
						<button class="ep-btn-cancel" id="ep-type-cancel">Cancel</button>
						<button class="ep-btn-save" id="ep-type-save">${is_edit ? 'Save' : 'Add'}</button>
					</div>
				</div>
			</div>
		`;
		$('body').append(html);

		$('#ep-type-cancel').on('click', () => $('#ep-type-dialog').remove());
		$('#ep-type-dialog').on('click', (e) => { if ($(e.target).is('#ep-type-dialog')) $('#ep-type-dialog').remove(); });

		$('#ep-type-save').on('click', () => {
			const type_name = $('#ep-type-name').val().trim();
			const assessment_type = $('#ep-type-atype').val();
			if (!type_name) { frappe.msgprint(__('Please enter a type name.')); return; }
			frappe.call({
				method: 'slcm.slcm.page.examination_planner.examination_planner.save_assessment_type',
				args: { type_name, assessment_type, name: data.name || null },
				freeze: true,
				callback: (r) => {
					$('#ep-type-dialog').remove();
					frappe.show_alert({ message: __('Assessment type saved.'), indicator: 'green' });
					this._assessment_types = null;
					this._fetch_types('');
				}
			});
		});
	}

	// ── SCHEMAS TAB ──────────────────────────────────────
	load_schemas(search = '') {
		$('#ep-tab-content').html(this._toolbar('Search by Evaluation Schema Name', '+ Create', 'show_schema_editor'));
		$('#ep-tab-content').append('<div id="ep-content-area"></div>');
		this._fetch_schemas(search);

		$('#ep-tab-content').on('input', '.ep-search', (e) => {
			clearTimeout(this._schema_search_timer);
			this._schema_search_timer = setTimeout(() => this._fetch_schemas(e.target.value), 300);
		});
		$('#ep-tab-content').on('click', '.ep-btn-primary', () => this.show_schema_editor());
		$('#ep-tab-content').on('click', '.ep-schema-link', (e) => {
			e.preventDefault();
			const name = $(e.currentTarget).data('name');
			this.show_schema_editor(name);
		});
	}

	_fetch_schemas(search) {
		$('#ep-content-area').html('<div class="ep-loading">Loading</div>');
		frappe.call({
			method: 'slcm.slcm.page.examination_planner.examination_planner.get_schemas',
			args: { search: search || '' },
			callback: (r) => {
				const data = r.message || [];
				if (!data.length) {
					$('#ep-content-area').html('<div class="ep-empty">No evaluation schemas found.</div>');
					return;
				}
				let rows = data.map(d => `
					<tr>
						<td class="link-cell">
							<a href="#" class="ep-schema-link" data-name="${d.name}">${d.schema_name}</a>
						</td>
						<td>${d.description || ''}</td>
						<td>${d.total_marks || 100}</td>
						<td>${d.assigned_courses || 0}</td>
					</tr>
				`).join('');
				$('#ep-content-area').html(`
					<table class="ep-list-table">
						<thead>
							<tr>
								<th>Name</th>
								<th>Description</th>
								<th>Total Marks</th>
								<th>Assigned Courses</th>
							</tr>
						</thead>
						<tbody>${rows}</tbody>
					</table>
				`);
			}
		});
	}

	// ── Schema Editor ──────────────────────────────────────
	show_schema_editor(schema_name) {
		// Ensure components and assessment types are loaded
		Promise.all([
			this._load_all_components(),
			this._load_all_assessment_types()
		]).then(() => {
			if (schema_name) {
				// Edit existing
				frappe.call({
					method: 'slcm.slcm.page.examination_planner.examination_planner.get_schema_detail',
					args: { name: schema_name },
					callback: (r) => {
						this._open_schema_modal(r.message, true);
					}
				});
			} else {
				// New schema
				this._open_schema_modal({
					name: null,
					schema_name: '',
					description: '',
					total_marks: 100,
					passing_marks: 40,
					schema_components: [],
					assessment_configs: [],
					reexam_configs: []
				}, false);
			}
		});
	}

	_load_all_components() {
		if (this._components) return Promise.resolve(this._components);
		return new Promise(resolve => {
			frappe.call({
				method: 'slcm.slcm.page.examination_planner.examination_planner.get_components',
				callback: (r) => {
					this._components = r.message || [];
					resolve(this._components);
				}
			});
		});
	}

	_load_all_assessment_types() {
		if (this._assessment_types) return Promise.resolve(this._assessment_types);
		return new Promise(resolve => {
			frappe.call({
				method: 'slcm.slcm.page.examination_planner.examination_planner.get_assessment_types',
				callback: (r) => {
					this._assessment_types = r.message || [];
					resolve(this._assessment_types);
				}
			});
		});
	}

	_open_schema_modal(schema, is_edit) {
		$('#ep-schema-modal').remove(); // remove any existing
		this._schema_state = JSON.parse(JSON.stringify(schema)); // deep copy

		const comp_options = (this._components || []).map(c =>
			`<option value="${c.name}">${c.component_name}</option>`
		).join('');

		const at_options = (this._assessment_types || []).map(a =>
			`<option value="${a.name}">${a.type_name || a.name}</option>`
		).join('');

		const modal_html = `
			<div class="ep-schema-overlay" id="ep-schema-modal">
				<div class="ep-schema-modal">
					<div class="ep-schema-modal-header">
						<h4>${__('Evaluation Schema')}</h4>
						<div class="ep-schema-modal-actions">
							<button class="ep-btn-cancel" id="ep-schema-cancel">Cancel</button>
							<button class="ep-btn-save" id="ep-schema-save">Save</button>
						</div>
					</div>
					<div class="ep-schema-modal-body">
						${is_edit ? `
						<div class="ep-alert" id="ep-schema-alert">
							<span>Schema is applied on Course(s). Partial editing of schema is not allowed.</span>
							<span class="close-btn" onclick="$(this).closest('.ep-alert').remove()">&#x2715;</span>
						</div>` : ''}

						<!-- Schema Details -->
						<div class="ep-form-section">
							<h5>${__('Schema Details')}</h5>
							<div class="ep-form-row">
								<div class="ep-form-group">
									<label>${__('Schema Name')}</label>
									<input type="text" id="ep-sname" value="${this._esc(schema.schema_name)}" placeholder="Enter Schema Name" ${is_edit ? 'readonly' : ''}/>
								</div>
							</div>
							<div class="ep-form-row single">
								<div class="ep-form-group">
									<label>${__('Description')}</label>
									<textarea id="ep-sdesc" rows="2" placeholder="Enter Schema Details">${this._esc(schema.description || '')}</textarea>
								</div>
							</div>
							<div class="ep-form-row">
								<div class="ep-form-group">
									<label>${__('Total Marks')}</label>
									<input type="number" id="ep-stotal" value="${schema.total_marks || 100}" placeholder="Total Marks"/>
								</div>
								<div class="ep-form-group">
									<label>${__('Passing Marks')}</label>
									<input type="number" id="ep-spassing" value="${schema.passing_marks || 0}" placeholder="Passing Marks"/>
								</div>
							</div>
						</div>

						<!-- Components Section -->
						<div class="ep-form-section">
							<h5>${__('Components')}</h5>
							<table class="ep-comp-table" id="ep-schema-comps-table">
								<thead>
									<tr>
										<th>${__('Component')}</th>
										<th>${__('Label')}</th>
										<th>${__('Effective Max. Marks')}</th>
										<th>${__('Weightage')}</th>
										<th>${__('Passing Marks')}</th>
										<th>${__('Consider For Pass/Fail')}</th>
										<th></th>
									</tr>
								</thead>
								<tbody id="ep-schema-comps-body"></tbody>
							</table>
							<div style="margin-top:8px;">
								<button class="ep-btn-add-row" id="ep-add-comp-row">+ Add Component</button>
							</div>
							<div class="ep-marks-summary" id="ep-comp-marks-summary">
								<span class="total" id="ep-comp-sum">0</span>
								<span>${__('Sum of effective maximum marks must be equal to schema total marks = ')} <span id="ep-comp-marks-eq">${schema.total_marks || 100}</span></span>
							</div>
						</div>

						<!-- Assessment Configuration per Component -->
						<div id="ep-assessment-sections"></div>
					</div>
				</div>
			</div>
		`;
		$('body').append(modal_html);

		// Render existing components
		schema.schema_components.forEach(c => this._add_comp_row(c));
		this._update_comp_marks_summary();
		this._render_assessment_sections(schema);

		// Event: close
		$('#ep-schema-cancel').on('click', () => $('#ep-schema-modal').remove());
		$('#ep-schema-modal').on('click', (e) => {
			if ($(e.target).is('#ep-schema-modal')) $('#ep-schema-modal').remove();
		});

		// Event: add component row
		$('#ep-add-comp-row').on('click', () => {
			this._add_comp_row({});
			this._update_comp_marks_summary();
		});

		// Event: save
		$('#ep-schema-save').on('click', () => this._save_schema());

		// Update total marks eq label dynamically
		$('#ep-stotal').on('input', () => {
			$('#ep-comp-marks-eq').text($('#ep-stotal').val() || 100);
			this._update_comp_marks_summary();
		});
	}

	_add_comp_row(data) {
		const comp_options = (this._components || []).map(c =>
			`<option value="${c.name}" ${data.component === c.name ? 'selected' : ''}>${c.component_name}</option>`
		).join('');
		const ctype = this._get_comp_type_by_name(data.component);
		const is_custom = !ctype || ctype === 'Custom';
		const row_id = 'comp-row-' + Date.now() + Math.random().toString(36).substr(2, 5);

		const $row = $(`
			<tr data-row-id="${row_id}" class="ep-comp-row">
				<td>
					<select class="ep-comp-select" name="component">
						<option value="">Select</option>
						${comp_options}
					</select>
					${data.component_type ? `<span class="ep-badge ${this._badge_class(data.component_type)}" style="margin-left:4px;font-size:10px;">${this._badge_label(data.component_type)}</span>` : ''}
				</td>
				<td><input type="text" name="label" value="${this._esc(data.label || '')}" placeholder="Label"/></td>
				<td><input type="number" name="effective_max_marks" value="${data.effective_max_marks || ''}" placeholder="--" ${!is_custom ? 'readonly' : ''}/></td>
				<td>
					<input type="number" name="weightage" value="${data.weightage !== undefined ? data.weightage : 100}" placeholder="--" ${!is_custom ? 'readonly' : ''}/> %
				</td>
				<td><input type="number" name="passing_marks" value="${data.passing_marks || ''}" placeholder="--" ${!is_custom ? 'readonly' : ''}/></td>
				<td style="text-align:center;">
					<input type="checkbox" name="consider_for_pass_fail" ${data.consider_for_pass_fail ? 'checked' : ''} ${!is_custom ? 'disabled' : ''}/>
				</td>
				<td>
					<button class="ep-btn-del-row ep-del-comp-row" data-row="${row_id}">&#x2715;</button>
				</td>
			</tr>
		`);
		$('#ep-schema-comps-body').append($row);

		// On component change - update type badge and enable/disable fields
		$row.find('.ep-comp-select').on('change', (e) => {
			const comp_name = $(e.target).val();
			const ctype = this._get_comp_type_by_name(comp_name);
			const is_cust = !ctype || ctype === 'Custom';
			const $r = $(e.target).closest('tr');
			$r.find('input[name=effective_max_marks], input[name=weightage], input[name=passing_marks]').prop('readonly', !is_cust);
			$r.find('input[name=consider_for_pass_fail]').prop('disabled', !is_cust);
			// Update badge
			const $badge = $r.find('.ep-badge');
			if (ctype) {
				const cls = this._badge_class(ctype);
				$badge.attr('class', `ep-badge ${cls}`).text(this._badge_label(ctype)).show();
			} else {
				$badge.hide();
			}
			this._update_comp_marks_summary();
			this._render_assessment_sections_from_state();
		});

		$row.find('input[name=effective_max_marks]').on('input', () => {
			this._update_comp_marks_summary();
			const comp_name = $row.find('select[name=component]').val();
			if (comp_name) {
				const val = parseFloat($row.find('input[name=effective_max_marks]').val()) || 0;
				$(`#ep-assessment-sections .ep-sub-section[data-comp="${comp_name}"] .assess-eq`).text(val);
			}
		});

		// Delete row
		$('#ep-schema-comps-body').on('click', `.ep-del-comp-row[data-row="${row_id}"]`, () => {
			$row.remove();
			this._update_comp_marks_summary();
			this._render_assessment_sections_from_state();
		});
	}

	_get_comp_type_by_name(comp_name) {
		if (!comp_name) return null;
		const comp = (this._components || []).find(c => c.name === comp_name);
		return comp ? comp.component_type : null;
	}

	_update_comp_marks_summary() {
		let total = 0;
		$('#ep-schema-comps-body .ep-comp-row').each(function () {
			const comp = $(this).find('select[name=component]').val();
			// Only count if it's a custom component
			const val = parseFloat($(this).find('input[name=effective_max_marks]').val()) || 0;
			total += val;
		});
		$('#ep-comp-sum').text(total);
	}

	// ── Assessment Sections ──────────────────────────────
	_render_assessment_sections(schema) {
		const $container = $('#ep-assessment-sections');
		$container.empty();

		schema.schema_components.forEach(comp => {
			const ctype = this._get_comp_type_by_name(comp.component);
			if (!comp.component) return;
			const comp_info = (this._components || []).find(c => c.name === comp.component);
			const comp_label = comp.label || (comp_info ? comp_info.component_name : comp.component);
			const type_label = ctype || 'Custom';

			if (ctype === 'Re Exam' || ctype === 'Makeup') {
				this._render_reexam_section($container, comp, schema.reexam_configs);
			} else {
				this._render_custom_section($container, comp, comp_label, type_label, schema.assessment_configs);
			}
		});
	}

	_render_assessment_sections_from_state() {
		// Rebuild sections from current UI state
		const $container = $('#ep-assessment-sections');
		$container.empty();
		const comp_names = [];

		$('#ep-schema-comps-body .ep-comp-row').each((i, row) => {
			const comp = $(row).find('select[name=component]').val();
			const label = $(row).find('input[name=label]').val();
			if (!comp) return;
			comp_names.push(comp);
			const ctype = this._get_comp_type_by_name(comp);
			const comp_info = (this._components || []).find(c => c.name === comp);
			const comp_label = label || (comp_info ? comp_info.component_name : comp);
			const type_label = ctype || 'Custom';

			if (ctype === 'Re Exam' || ctype === 'Makeup') {
				const existing_reexam = (this._schema_state.reexam_configs || []).filter(r => r.component === comp);
				this._render_reexam_section($container, { component: comp, label: comp_label }, existing_reexam);
			} else {
				const existing_assess = (this._schema_state.assessment_configs || []).filter(a => a.component === comp);
				const $comp_row = $('#ep-schema-comps-body .ep-comp-row').filter(function() {
					return $(this).find('select[name=component]').val() === comp;
				});
				const comp_eff_marks = parseFloat($comp_row.find('input[name=effective_max_marks]').val()) || 0;
				this._render_custom_section($container, { component: comp, label: comp_label, effective_max_marks: comp_eff_marks }, comp_label, type_label, existing_assess);
			}
		});
	}

	_render_custom_section($container, comp, comp_label, type_label, existing_assessments) {
		const at_options = (this._assessment_types || []).map(a =>
			`<option value="${a.name}">${a.type_name || a.name}</option>`
		).join('');

		const section_id = 'assess-' + comp.component.replace(/\s+/g, '-');
		const $section = $(`
			<div class="ep-sub-section" id="${section_id}" data-comp="${comp.component}">
				<div class="ep-sub-section-header">
					<span class="ep-sub-section-title">${comp_label} | ${comp_label}</span>
					<div style="display:flex;align-items:center;gap:8px;">
						<span class="ep-badge ep-badge-custom">${type_label}</span>
						<button class="ep-btn-add-row ep-add-assess-row" data-comp="${comp.component}" data-section="${section_id}">+ Add Assessment</button>
					</div>
				</div>
				<div style="overflow-x:auto;">
					<table class="ep-comp-table" style="min-width:700px;">
						<thead>
							<tr>
								<th>${__('Assessment')}</th>
								<th>${__('Label')}</th>
								<th>${__('Effective Marks')}</th>
								<th>${__('Maximum Marks')}</th>
								<th>${__('Minimum Marks')}</th>
								<th>${__('Passing Marks')}</th>
								<th>${__('Consider For Pass/Fail')}</th>
								<th>${__('Weightage')}</th>
								<th>${__('Enrollment')}</th>
								<th></th>
							</tr>
						</thead>
						<tbody class="assess-body"></tbody>
					</table>
				</div>
				<div class="ep-marks-summary">
					<span class="total assess-sum">0</span>
					<span>${__('Sum of effective maximum marks must be equal to component effective total marks = ')} <span class="assess-eq">${comp.effective_max_marks || 0}</span></span>
				</div>
			</div>
		`);
		$container.append($section);

		// Add existing rows
		const rows_data = existing_assessments.filter(a => a.component === comp.component);
		rows_data.forEach(a => this._add_assess_row($section, a, at_options));
		if (!rows_data.length) this._add_assess_row($section, {}, at_options);

		this._update_assess_sum($section);

		// Add row button
		$section.on('click', '.ep-add-assess-row', () => {
			this._add_assess_row($section, {}, at_options);
		});
	}

	_add_assess_row($section, data, at_options) {
		const row_id = 'ar-' + Date.now() + Math.random().toString(36).substr(2, 5);
		// build options with current selection
		const opts = (this._assessment_types || []).map(a =>
			`<option value="${a.name}" ${data.assessment_type === a.name ? 'selected' : ''}>${a.type_name || a.name}</option>`
		).join('');
		const at_info = data.assessment_type ? (this._assessment_types || []).find(a => a.name === data.assessment_type) : null;
		const at_badge = at_info ? `<span class="ep-badge ${this._badge_class(at_info.assessment_type)}" style="font-size:10px;">${this._badge_label(at_info.assessment_type)}</span>` : '';

		const $row = $(`
			<tr data-row-id="${row_id}">
				<td>
					<select name="assessment_type" style="min-width:130px;">
						<option value="">Select</option>
						${opts}
					</select>
					${at_badge}
				</td>
				<td><input type="text" name="label" value="${this._esc(data.label || '')}" placeholder="Label" style="width:90px;"/></td>
				<td><input type="number" name="effective_marks" value="${data.effective_marks || ''}" placeholder="0" style="width:70px;" readonly/></td>
				<td><input type="number" name="maximum_marks" value="${data.maximum_marks || ''}" placeholder="0" style="width:70px;"/></td>
				<td><input type="number" name="minimum_marks" value="${data.minimum_marks || 0}" placeholder="0" style="width:60px;"/></td>
				<td><input type="number" name="passing_marks" value="${data.passing_marks || 0}" placeholder="0" style="width:60px;"/></td>
				<td style="text-align:center;"><input type="checkbox" name="consider_for_pass_fail" ${data.consider_for_pass_fail ? 'checked' : ''}/></td>
				<td><input type="number" name="weightage" value="${data.weightage !== undefined ? data.weightage : 100}" style="width:60px;"/> %</td>
				<td>
					<select name="enrollment" style="min-width:70px;">
						<option value="Auto" ${(data.enrollment || 'Auto') === 'Auto' ? 'selected' : ''}>Auto</option>
						<option value="Manual" ${data.enrollment === 'Manual' ? 'selected' : ''}>Manual</option>
					</select>
				</td>
				<td><button class="ep-btn-del-row ep-del-assess-row">&#x2715;</button></td>
			</tr>
		`);
		$section.find('.assess-body').append($row);

		const _calc_eff = () => {
			const wt = parseFloat($row.find('input[name=weightage]').val()) || 0;
			const max = parseFloat($row.find('input[name=maximum_marks]').val()) || 0;
			const eff = Math.round((wt / 100) * max * 100) / 100;
			$row.find('input[name=effective_marks]').val(eff || '');
			this._update_assess_sum($section);
		};
		$row.find('input[name=weightage], input[name=maximum_marks]').on('input', _calc_eff);
		$row.on('click', '.ep-del-assess-row', () => {
			$row.remove();
			this._update_assess_sum($section);
		});

		// Update badge on assessment type change
		$row.find('select[name=assessment_type]').on('change', (e) => {
			const aname = $(e.target).val();
			const at_info = (this._assessment_types || []).find(a => a.name === aname);
			let $badge = $row.find('.ep-badge');
			if ($badge.length === 0) {
				$(e.target).after('<span class="ep-badge" style="font-size:10px;margin-left:4px;"></span>');
				$badge = $row.find('.ep-badge');
			}
			if (at_info) {
				$badge.attr('class', `ep-badge ${this._badge_class(at_info.assessment_type)}`).text(this._badge_label(at_info.assessment_type)).show();
			} else {
				$badge.hide();
			}
		});
	}

	_update_assess_sum($section) {
		let total = 0;
		$section.find('.assess-body tr').each(function () {
			total += parseFloat($(this).find('input[name=effective_marks]').val()) || 0;
		});
		$section.find('.assess-sum').text(total);
	}

	_render_reexam_section($container, comp, existing_reexam) {
		const section_id = 're-' + comp.component.replace(/\s+/g, '-');
		const rows_data = existing_reexam.filter ? existing_reexam.filter(r => r.component === comp.component) : existing_reexam;

		const at_options = (this._assessment_types || []).map(a =>
			`<option value="${a.name}">${a.type_name || a.name}</option>`
		).join('');

		const $section = $(`
			<div class="ep-sub-section" id="${section_id}" data-comp="${comp.component}">
				<div class="ep-sub-section-header">
					<span class="ep-sub-section-title">${comp.label || comp.component} | ${comp.label || comp.component}</span>
					<div style="display:flex;align-items:center;gap:8px;">
						<select class="re-type-cat" style="padding:4px 8px;border:1px solid #ddd;border-radius:3px;font-size:12px;">
							<option value="Assessment">Assessment</option>
							<option value="ReExam/Makeup Assessment">ReExam/Makeup</option>
						</select>
						<span class="ep-badge ep-badge-reexam">Re Exam</span>
						<button class="ep-btn-add-row ep-add-reexam-row" data-section="${section_id}">+ Add</button>
					</div>
				</div>
				<div style="overflow-x:auto;">
					<table class="ep-comp-table" style="min-width:600px;">
						<thead>
							<tr>
								<th>${__('Assessment')}</th>
								<th>${__('Label')}</th>
								<th>${__('Maximum Marks')}</th>
								<th>${__('Minimum Marks')}</th>
								<th>${__('Passing Marks')}</th>
								<th>${__('Enrollment')}</th>
								<th></th>
							</tr>
						</thead>
						<tbody class="reexam-body"></tbody>
					</table>
				</div>
			</div>
		`);
		$container.append($section);

		rows_data.forEach(r => this._add_reexam_row($section, r, at_options, comp.component));
		if (!rows_data.length) this._add_reexam_row($section, {}, at_options, comp.component);

		$section.on('click', '.ep-add-reexam-row', () => {
			this._add_reexam_row($section, {}, at_options, comp.component);
		});
	}

	_add_reexam_row($section, data, at_options, comp_name) {
		const row_id = 'rr-' + Date.now() + Math.random().toString(36).substr(2, 5);
		const opts = (this._assessment_types || []).map(a =>
			`<option value="${a.name}" ${data.assessment_type === a.name ? 'selected' : ''}>${a.type_name || a.name}</option>`
		).join('');
		const sub_at_opts = (this._assessment_types || []).map(a =>
			`<option value="${a.name}" ${data.substitute_for === a.name ? 'selected' : ''}>${a.type_name || a.name}</option>`
		).join('');

		const show_subst = data.substitute_for ? '' : 'display:none;';
		const subst_label = data.substitute_for ? __('Hide Substitution Settings') : __('Show Substitution Settings');

		const $row = $(`
			<tr data-row-id="${row_id}" data-comp="${comp_name}">
				<td>
					<select name="assessment_type" style="min-width:130px;">
						<option value="">Select</option>
						${opts}
					</select>
				</td>
				<td><input type="text" name="label" value="${this._esc(data.label || '')}" placeholder="Label" style="width:90px;"/></td>
				<td><input type="number" name="maximum_marks" value="${data.maximum_marks || ''}" placeholder="0" style="width:70px;"/></td>
				<td><input type="number" name="minimum_marks" value="${data.minimum_marks || 0}" placeholder="0" style="width:60px;"/></td>
				<td><input type="number" name="passing_marks" value="${data.passing_marks || 0}" placeholder="0" style="width:60px;"/></td>
				<td>
					<select name="enrollment" style="min-width:70px;">
						<option value="Auto" ${(data.enrollment || 'Manual') === 'Auto' ? 'selected' : ''}>Auto</option>
						<option value="Manual" ${(data.enrollment || 'Manual') === 'Manual' ? 'selected' : ''}>Manual</option>
					</select>
				</td>
				<td><button class="ep-btn-del-row ep-del-reexam-row">&#x2715;</button></td>
			</tr>
			<tr data-row-id="${row_id}-subst" data-comp="${comp_name}" class="subst-row">
				<td colspan="7">
					<span class="ep-subst-toggle" data-row="${row_id}">${subst_label}</span>
					<div class="ep-subst-settings" style="${show_subst}">
						<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;">
							<div class="ep-form-group">
								<label>${__('Substitute For')}</label>
								<select name="substitute_for">
									<option value="">Select</option>
									${sub_at_opts}
								</select>
							</div>
							<div class="ep-form-group">
								<label>${__('Weightage')}</label>
								<input type="number" name="substitute_weightage" value="${data.substitute_weightage || 100}" placeholder="100"/> %
							</div>
							<div class="ep-form-group">
								<label>${__('Effective marks')}</label>
								<input type="number" name="effective_marks" value="${data.effective_marks || ''}" readonly/>
							</div>
							<div class="ep-form-group">
								<label>${__('Substitute assessment effective marks')}</label>
								<input type="number" name="sub_effective_marks" value="${data.effective_marks || ''}" readonly/>
							</div>
						</div>
					</div>
				</td>
			</tr>
		`);
		$section.find('.reexam-body').append($row);

		// Toggle substitution settings
		$row.on('click', '.ep-subst-toggle', function () {
			const $settings = $(this).next('.ep-subst-settings');
			const $r = $(`[data-row-id="${row_id}-subst"]`);
			$r.find('.ep-subst-settings').toggle();
			$(this).text($r.find('.ep-subst-settings').is(':visible') ? __('Hide Substitution Settings') : __('Show Substitution Settings'));
		});

		$row.on('click', '.ep-del-reexam-row', () => {
			$(`[data-row-id="${row_id}"]`).remove();
			$(`[data-row-id="${row_id}-subst"]`).remove();
		});
	}

	// ── Save Schema ──────────────────────────────────────
	_save_schema() {
		const schema_name = $('#ep-sname').val().trim();
		const description = $('#ep-sdesc').val().trim();
		const total_marks = parseFloat($('#ep-stotal').val()) || 100;
		const passing_marks = parseFloat($('#ep-spassing').val()) || 0;

		if (!schema_name) { frappe.msgprint(__('Please enter a schema name.')); return; }

		// Collect components
		const schema_components = [];
		$('#ep-schema-comps-body .ep-comp-row').each((i, row) => {
			const component = $(row).find('select[name=component]').val();
			if (!component) return;
			schema_components.push({
				component: component,
				label: $(row).find('input[name=label]').val() || '',
				effective_max_marks: parseFloat($(row).find('input[name=effective_max_marks]').val()) || 0,
				weightage: parseFloat($(row).find('input[name=weightage]').val()) || 100,
				passing_marks: parseFloat($(row).find('input[name=passing_marks]').val()) || 0,
				consider_for_pass_fail: $(row).find('input[name=consider_for_pass_fail]').is(':checked') ? 1 : 0,
			});
		});

		// Collect assessment configs (custom sections)
		const assessment_configs = [];
		$('#ep-assessment-sections .ep-sub-section:not([id^="re-"])').each((i, section) => {
			const comp_name = $(section).attr('data-comp');
			$(section).find('.assess-body tr').each((j, row) => {
				const at = $(row).find('select[name=assessment_type]').val();
				if (!at) return;
				assessment_configs.push({
					component: comp_name,
					assessment_type: at,
					label: $(row).find('input[name=label]').val() || '',
					effective_marks: parseFloat($(row).find('input[name=effective_marks]').val()) || 0,
					maximum_marks: parseFloat($(row).find('input[name=maximum_marks]').val()) || 0,
					minimum_marks: parseFloat($(row).find('input[name=minimum_marks]').val()) || 0,
					passing_marks: parseFloat($(row).find('input[name=passing_marks]').val()) || 0,
					consider_for_pass_fail: $(row).find('input[name=consider_for_pass_fail]').is(':checked') ? 1 : 0,
					weightage: parseFloat($(row).find('input[name=weightage]').val()) || 100,
					enrollment: $(row).find('select[name=enrollment]').val() || 'Auto',
				});
			});
		});

		// Collect reexam configs
		const reexam_configs = [];
		$('#ep-assessment-sections .ep-sub-section[id^="re-"]').each((i, section) => {
			const comp_name = $(section).attr('data-comp');
			$(section).find('.reexam-body tr:not(.subst-row)').each((j, row) => {
				const at = $(row).find('select[name=assessment_type]').val();
				if (!at) return;
				const row_id = $(row).attr('data-row-id');
				const $subst_row = $(`[data-row-id="${row_id}-subst"]`);
				reexam_configs.push({
					component: comp_name,
					assessment_type: at,
					label: $(row).find('input[name=label]').val() || '',
					maximum_marks: parseFloat($(row).find('input[name=maximum_marks]').val()) || 0,
					minimum_marks: parseFloat($(row).find('input[name=minimum_marks]').val()) || 0,
					passing_marks: parseFloat($(row).find('input[name=passing_marks]').val()) || 0,
					enrollment: $(row).find('select[name=enrollment]').val() || 'Manual',
					substitute_for: $subst_row.find('select[name=substitute_for]').val() || null,
					substitute_weightage: parseFloat($subst_row.find('input[name=substitute_weightage]').val()) || 100,
					effective_marks: parseFloat($subst_row.find('input[name=effective_marks]').val()) || 0,
					re_exam_type_category: $(section).find('.re-type-cat').val() || 'Assessment',
				});
			});
		});

		const data = {
			name: this._schema_state.name || null,
			schema_name,
			description,
			total_marks,
			passing_marks,
			schema_components,
			assessment_configs,
			reexam_configs,
		};

		frappe.call({
			method: 'slcm.slcm.page.examination_planner.examination_planner.save_schema',
			args: { data: JSON.stringify(data) },
			freeze: true,
			callback: (r) => {
				$('#ep-schema-modal').remove();
				frappe.show_alert({ message: __('Schema saved successfully.'), indicator: 'green' });
				this._fetch_schemas('');
			},
			error: (r) => {
				frappe.msgprint(r.message || __('Failed to save schema.'));
			}
		});
	}

	// ── Shared Toolbar ──────────────────────────────────
	_toolbar(search_placeholder, btn_label) {
		return `
			<div class="ep-toolbar">
				<div class="ep-search-wrap">
					<span class="search-icon">
						<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
						</svg>
					</span>
					<input type="text" class="ep-search" placeholder="${__(search_placeholder)}"/>
				</div>
				<button class="ep-btn-primary">${__(btn_label)}</button>
			</div>
		`;
	}

	_esc(str) {
		if (!str) return '';
		return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
	}
}
