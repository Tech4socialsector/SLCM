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
                
                <!-- Performance Metrics Row -->
                <div class="metrics-row mb-4">
                    <div id="yield-metrics-container" class="glass-card performance-summary p-4">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Conversion & Yield Performance')}</h6>
                        </div>
                        <div id="yield-metrics-grid" class="d-flex justify-content-around mt-4">
                            <!-- Populated dynamically -->
                        </div>
                    </div>
                </div>

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

                    <!-- New Rows for Gender & Location -->
                    <div id="geographic-chart-card" class="chart-card glass-card">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Geographic Distribution')}</h6>
                            <span class="info-tag">${__('by State')}</span>
                        </div>
                        <div id="geographic-chart"></div>
                    </div>

                    <div id="gender-chart-card" class="chart-card glass-card">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Gender Diversity')}</h6>
                        </div>
                        <div id="gender-chart"></div>
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

                    <div id="fee-payment-card" class="chart-card glass-card">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Fee Payment Status')}</h6>
                        </div>
                        <div id="fee-payment-chart"></div>
                    </div>

                    <div id="offer-breakdown-card" class="chart-card glass-card full-width">
                        <div class="chart-header">
                            <h6 class="chart-title">${__('Offer Outcomes')}</h6>
                        </div>
                        <div id="offer-breakdown-chart"></div>
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
        this.add_filter('program', __('Programme'), 'Link', 'Programme');
        this.add_filter('whether_scstobc_ncl', __('Category'), 'Link', 'Admission Category');
        this.add_filter('date_range', __('Date Range'), 'DateRange');

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
        this.render_yield_metrics(data.yield_metrics || {});

        // Handle each chart with safety checks
        this.render_funnel_chart(data.funnel || []);
        this.render_trend_chart(data.trend || []);
        this.render_geographic_distribution(data.state_dist || []);
        this.render_gender_distribution(data.gender_dist || []);
        this.render_campus_distribution(data.campus_dist || []);
        this.render_program_distribution(data.program_dist || []);
        this.render_fee_payment_distribution(data.fee_payment_dist || []);
        this.render_offer_breakdown(data.offer_breakdown || []);
        this.render_category_distribution(data.category_dist || []);
    }

    render_yield_metrics(metrics) {
        let container = this.wrapper.find('#yield-metrics-grid').empty();
        const items = [
            { label: __('Final Yield Rate'), value: metrics.yield_rate || 0, sub: __('Enrolled / Total Offers'), color: 'bg-green' },
            { label: __('Applicant Conversion'), value: metrics.acceptance_rate || 0, sub: __('Enrolled / Selected'), color: 'bg-blue' }
        ];

        let html = items.map(i => `
            <div class="yield-item text-center">
                <div class="yield-label text-muted font-weight-bold mb-2">${i.label}</div>
                <div class="yield-value display-4 font-weight-bold mb-2" style="color: #1e293b">${i.value}%</div>
                <div class="progress mb-2" style="height: 10px; width: 250px; background: #f1f5f9; border-radius: 5px;">
                    <div class="progress-bar ${i.color}" role="progressbar" style="width: ${i.value}%; border-radius: 5px;"></div>
                </div>
                <div class="yield-sub text-muted small">${i.sub}</div>
            </div>
        `).join('<div class="vertical-divider mx-4" style="border-left: 1px solid #e2e8f0;"></div>');

        container.html(html);
    }

    render_summary(summary) {
        if (!summary) return;
        const cards = [
            { label: __('Total Applicants'), value: summary.total || 0, icon: 'fa fa-users', color: 'icon-blue' },
            { label: __('Submitted'), value: summary.submitted || 0, icon: 'fa fa-paper-plane', color: 'icon-purple' },
            { label: __('Selected'), value: summary.selected || 0, icon: 'fa fa-user-plus', color: 'icon-green' },
            { label: __('Offers'), value: summary.offers || 0, icon: 'fa fa-envelope-open', color: 'icon-yellow' },
            { label: __('Waitlisted'), value: summary.waitlisted || 0, icon: 'fa fa-clock-o', color: 'icon-teal' },
            { label: __('Enrolled'), value: summary.enrolled || 0, icon: 'fa fa-graduation-cap', color: 'icon-green' },
            { label: __('Rejected'), value: summary.rejected || 0, icon: 'fa fa-user-times', color: 'icon-red' },
        ];

        let html = cards.map(c => `
            <div class="summary-card glass-card" style="z-index: 1;">
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

    render_geographic_distribution(dist) {
        let container = $("#geographic-chart").empty();
        if (!dist.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        new frappe.Chart("#geographic-chart", {
            data: {
                labels: dist.map(d => d.label),
                datasets: [{ values: dist.map(d => d.count) }]
            },
            type: 'bar',
            height: 300,
            axisOptions: {
                xIsSeries: true
            },
            colors: ['#f43f5e']
        });
    }

    render_gender_distribution(dist) {
        let container = $("#gender-chart").empty();
        if (!dist.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        new frappe.Chart("#gender-chart", {
            data: {
                labels: dist.map(d => d.label),
                datasets: [{ values: dist.map(d => d.count) }]
            },
            type: 'pie',
            height: 300,
            colors: ['#ec4899', '#3b82f6', '#94a3b8']
        });
    }

    render_offer_breakdown(dist) {
        let container = $("#offer-breakdown-chart").empty();
        if (!dist.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        new frappe.Chart("#offer-breakdown-chart", {
            data: {
                labels: dist.map(d => d.label),
                datasets: [{ values: dist.map(d => d.count) }]
            },
            type: 'bar',
            height: 300,
            axisOptions: {
                xIsSeries: true
            },
            colors: ['#f59e0b']
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
                datasets: [{ values: dist.map(d => d.count) }]
            },
            type: 'bar', // Switched to bar for better readability when many campuses exist
            height: 300,
            axisOptions: {
                xIsSeries: true // Horizontal bar
            },
            colors: ['#10b981']
        });
    }

    render_program_distribution(dist) {
        let container = $("#program-chart").empty();
        if (!dist.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        // Use Horizontal Bar chart for programs. 
        // Pie charts fail when you have more than 5-7 categories as labels overlap.
        new frappe.Chart("#program-chart", {
            data: {
                labels: dist.map(d => d.label),
                datasets: [{ values: dist.map(d => d.count) }]
            },
            type: 'bar',
            height: 300,
            axisOptions: {
                xIsSeries: true // Makes it a horizontal bar chart
            },
            colors: ['#0ea5e9']
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

    render_fee_payment_distribution(dist) {
        let container = $("#fee-payment-chart").empty();
        if (!dist.length) {
            container.append(`<div class="text-center p-5 text-muted">${__('No data available')}</div>`);
            return;
        }

        new frappe.Chart("#fee-payment-chart", {
            data: {
                labels: dist.map(d => d.label),
                datasets: [{ values: dist.map(d => d.count) }]
            },
            type: 'pie',
            height: 300,
            colors: ['#10b981', '#f59e0b', '#3b82f6', '#f43f5e', '#64748b']
        });
    }
}
