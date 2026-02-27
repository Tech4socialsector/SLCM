frappe.pages['admission-flow-dashboard'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Admission Flow Master Dashboard'),
        single_column: true
    });

    new AdmissionDashboard(wrapper);
}

class AdmissionDashboard {
    constructor(wrapper) {
        this.wrapper = $(wrapper);
        this.page = wrapper.page;
        this.filters = {};
        this.init();
    }

    init() {
        this.render_skeleton();
        this.setup_filters();
        this.refresh();
    }

    render_skeleton() {
        this.wrapper.html(`
            <div class="dashboard-wrapper">
                <div id="filter-container"></div>
                <div class="summary-grid" id="summary-cards"></div>
                <div class="charts-grid">
                    <div id="funnel-chart-card" class="chart-card glass-card">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Admission Pipeline')}</h6>
                            <span class="info-tag">${__('Funnel View')}</span>
                        </div>
                        <div id="funnel-chart"></div>
                    </div>
                    <div id="trend-chart-card" class="chart-card glass-card">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Application Trends')}</h6>
                            <span class="info-tag">${__('Last 30 Days')}</span>
                        </div>
                        <div id="trend-chart"></div>
                    </div>
                    <div id="campus-chart-card" class="chart-card glass-card">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Distribution by Campus')}</h6>
                        </div>
                        <div id="campus-chart"></div>
                    </div>
                    <div id="program-chart-card" class="chart-card glass-card">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Primary Program Choice')}</h6>
                        </div>
                        <div id="program-chart"></div>
                    </div>
                    <div id="category-chart-card" class="chart-card glass-card full-width">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Category-wise Breakdown')}</h6>
                        </div>
                        <div id="category-chart"></div>
                    </div>
                </div>
            </div>
        `);
    }

    setup_filters() {
        let me = this;
        this.filter_bar = this.wrapper.find('#filter-container');
        this.filter_bar.addClass('filter-bar glass-card');

        // Add filters
        this.add_filter('admission_year', __('Admission Year'), 'Link', 'Admission Year');
        this.add_filter('admission_cycle', __('Admission Cycle'), 'Link', 'Admission Cycle');
        this.add_filter('campus', __('Campus'), 'Link', 'Campus');
        this.add_filter('program', __('Program'), 'Link', 'Program');
        this.add_filter('reservation_category', __('Category'), 'Link', 'Admission Category');

        // Clear button in the filter bar
        this.clear_btn = $(`<button class="btn btn-default btn-sm" style="margin-left: auto; height: 35px; align-self: flex-end; margin-bottom: 2px;">
            <i class="fa fa-refresh"></i> ${__('Reset')}
        </button>`).appendTo(this.filter_bar).on('click', () => {
            Object.keys(this.page.fields_dict).forEach(f => this.page.fields_dict[f].set_value(""));
            this.filters = {};
            this.refresh();
        });

        // Related Filter Logic: Admission Cycle depends on Admission Year
        this.page.fields_dict.admission_cycle.get_query = function () {
            return {
                filters: { 'admission_year': me.filters.admission_year || "" }
            };
        };

        // Initialize Defaults
        const year = frappe.defaults.get_user_default("admission_year");
        if (year) {
            this.page.fields_dict.admission_year.set_value(year);
            this.filters.admission_year = year;
        }

        const cycle = frappe.defaults.get_user_default("admission_cycle");
        if (cycle) {
            this.page.fields_dict.admission_cycle.set_value(cycle);
            this.filters.admission_cycle = cycle;
        }
    }

    add_filter(fieldname, label, fieldtype, options, reqd = 0) {
        let me = this;
        let field = this.page.add_field({
            fieldname: fieldname,
            label: label,
            fieldtype: fieldtype,
            options: options,
            reqd: reqd,
            change: function () {
                let val = this.get_value();
                me.filters[fieldname] = val;
                me.refresh();
            }
        });

        // Append to our custom filter container
        field.$wrapper.appendTo(this.filter_bar);

        // Ensure the label exists and is styled professionally
        let label_el = field.$wrapper.find('label');
        if (label_el.length === 0) {
            // Some Frappe versions don't add the label inside $wrapper for page fields
            $(`<label>${label}</label>`).prependTo(field.$wrapper);
            label_el = field.$wrapper.find('label');
        }

        // Apply robust styling for visibility
        field.$wrapper.css({
            'min-width': '220px',
            'margin-bottom': '10px !important',
            'display': 'flex',
            'flex-direction': 'column'
        });

        label_el.css({
            'display': 'block',
            'font-weight': '700',
            'font-size': '12px',
            'color': '#64748b',
            'margin-bottom': '8px',
            'text-transform': 'uppercase'
        });

        // Ensure input has height
        field.$wrapper.find('input, select').css({
            'height': '40px',
            'border-radius': '8px'
        });
    }

    refresh() {
        let me = this;

        this.wrapper.find('.charts-grid').css('opacity', '1').css('pointer-events', 'all');
        this.show_loader();

        frappe.call({
            method: 'slcm.admission.page.admission_flow_dashboard.admission_flow_dashboard.get_dashboard_data',
            args: { filters: this.filters },
            callback: function (r) {
                me.render_data(r.message);
            }
        });
    }

    show_loader() {
        // Maybe add some subtle opacity to cards
    }

    render_data(data) {
        if (!data) return;
        this.render_summary(data.summary);

        // Handle each chart with safety checks
        this.render_funnel_chart(data.funnel || []);
        this.render_trend_chart(data.trend || []);
        this.render_campus_distribution(data.campus_dist || []);
        this.render_program_distribution(data.program_dist || []);
        this.render_category_distribution(data.category_dist || []);
    }

    render_summary(summary) {
        if (!summary) return;
        const cards = [
            { label: __('Total Applicants'), value: summary.total || 0, icon: 'fa fa-users', color: 'icon-blue' },
            { label: __('Submitted'), value: summary.submitted || 0, icon: 'fa fa-paper-plane', color: 'icon-purple' },
            { label: __('Selected'), value: summary.selected || 0, icon: 'fa fa-user-check', color: 'icon-green' },
            { label: __('Offers'), value: summary.offers || 0, icon: 'fa fa-envelope-open', color: 'icon-yellow' },
            { label: __('Waitlisted'), value: summary.waitlisted || 0, icon: 'fa fa-clock-o', color: 'icon-teal' },
            { label: __('Enrolled'), value: summary.enrolled || 0, icon: 'fa fa-graduation-cap', color: 'icon-green' },
            { label: __('Rejected'), value: summary.rejected || 0, icon: 'fa fa-user-times', color: 'icon-red' },
        ];

        let html = cards.map(c => `
            <div class="summary-card glass-card">
                <div class="card-icon ${c.color}">
                    <i class="${c.icon}"></i>
                </div>
                <div>
                    <div class="card-label">${c.label}</div>
                    <div class="card-value">${c.value}</div>
                </div>
            </div>
        `).join('');

        this.wrapper.find('#summary-cards').html(html);
    }

    render_funnel_chart(funnel) {
        let container = $("#funnel-chart").empty();
        if (!funnel.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        new frappe.Chart("#funnel-chart", {
            data: {
                labels: funnel.map(f => f.label),
                datasets: [
                    {
                        name: __("Applicants"),
                        values: funnel.map(f => f.count)
                    }
                ]
            },
            type: 'bar', // Waterfall look with bar in descending order
            colors: ['#3b82f6'],
            height: 300,
            barOptions: {
                space_between_bars: 45
            }
        });
    }

    render_trend_chart(trend) {
        let container = $("#trend-chart").empty();
        if (!trend.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        // Line charts can crash with 1 data point in certain Frappe versions.
        // Fallback to bar in that case.
        let chart_type = trend.length > 1 ? 'line' : 'bar';

        new frappe.Chart("#trend-chart", {
            data: {
                labels: trend.map(t => {
                    if (!t.date) return "";
                    try {
                        let user_date = frappe.datetime.str_to_user(t.date);
                        return user_date ? user_date.split(',')[0] : t.date;
                    } catch (e) {
                        return t.date || "";
                    }
                }),
                datasets: [
                    {
                        name: __("Submissions"),
                        values: trend.map(t => parseInt(t.count || 0))
                    }
                ]
            },
            type: chart_type,
            height: 300,
            lineOptions: {
                hideDots: 0
            },
            colors: ['#8b5cf6']
        });
    }

    render_campus_distribution(dist) {
        let container = $("#campus-chart").empty();
        if (!dist.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        new frappe.Chart("#campus-chart", {
            data: {
                labels: dist.map(d => d.label),
                datasets: [
                    {
                        values: dist.map(d => d.count)
                    }
                ]
            },
            type: 'donut',
            height: 300,
            colors: ['#10b981', '#34d399', '#6ee7b7', '#a7f3d0']
        });
    }

    render_program_distribution(dist) {
        let container = $("#program-chart").empty();
        if (!dist.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        new frappe.Chart("#program-chart", {
            data: {
                labels: dist.map(d => d.label),
                datasets: [
                    {
                        values: dist.map(d => d.count)
                    }
                ]
            },
            type: 'pie',
            height: 300,
            colors: ['#0ea5e9', '#38bdf8', '#7dd3fc', '#bae6fd']
        });
    }

    render_category_distribution(dist) {
        let container = $("#category-chart").empty();
        if (!dist.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        new frappe.Chart("#category-chart", {
            data: {
                labels: dist.map(d => d.label),
                datasets: [
                    {
                        name: __("Applicants"),
                        values: dist.map(d => d.count)
                    }
                ]
            },
            type: 'bar',
            height: 300,
            axisOptions: {
                xIsSeries: true
            },
            colors: ['#f59e0b']
        });
    }
}
