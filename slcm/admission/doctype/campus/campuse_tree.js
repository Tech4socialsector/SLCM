frappe.provide("frappe.treeview_settings");

frappe.treeview_settings["Campus"] = {
    breadcrumb: "Campus",
    title: __("Univercity Tree"),
    get_tree_root: false,
    filters: [
        {
            fieldname: "campus",
            fieldtype: "Select",
            options: erpnext.utils.get_tree_options("campus"),
            label: __("campus"),
            default: erpnext.utils.get_tree_default("campus"),
            on_change: function () {
                var me = frappe.treeview_settings["Campus"].treeview;
                var campus = me.page.fields_dict.campus.get_value();
                if (!campus) {
                    frappe.throw(__("Please set a campus"));
                }
                frappe.call({
                    method: "slcm.admission.doctype.campus.campus.get_root_company",
                    args: {
                        campus: campus,
                    },
                    callback: function (r) {
                        if (r.message) {
                            let root_campus = r.message.length ? r.message[0] : "";
                            me.page.fields_dict.root_campus.set_value(root_company);

                            frappe.db.get_value(
                                "Campus",
                                { name: campus },
                                "allow_account_creation_against_child_company",
                                (r) => {
                                    frappe.flags.ignore_root_campus_validation =
                                        r.allow_account_creation_against_child_company;
                                }
                            );
                        }
                    },
                });
            },
        },
        {
            fieldname: "root_campus",
            fieldtype: "Data",
            label: __("Root Campus"),
            hidden: true,
            disable_onchange: true,
        },
    ],
    root_label: "Campus",

    get_tree_nodes: "path.to.whitelisted_method.get_children",
    add_tree_node: "path.to.whitelisted_method.handle_add_account",

    fields: [
        {
            fieldtype: "Data",
            fieldname: "account_name",
            label: "New Account Name",
            reqd: true,
        },
        {
            fieldtype: "Link",
            fieldname: "account_currency",
            label: "Currency",
            options: "Currency",
        },
        {
            fieldtype: "Check",
            fieldname: "is_group",
            label: "Is Group",
        },
    ],

    ignore_fields: ["parent_account"],

    menu_items: [
        {
            label: "New Company",
            action: function () {
                frappe.new_doc("Company", true);
            },
            condition: "frappe.boot.user.can_create.indexOf('Company') !== -1",
        },
    ],

    onload: function (treeview) { },

    post_render: function (treeview) { },

    onrender: function (node) { },

    on_get_node: function (nodes) { },

    extend_toolbar: true,

    toolbar: [
        {
            label: "Add Child",
            condition: function (node) {
                return node && node.is_group;
            },
            click: function (node) {
                frappe.treeview_settings["Campus"].add_node(node);
            },
            btnClass: "hidden-xs",
        },
    ],
};
