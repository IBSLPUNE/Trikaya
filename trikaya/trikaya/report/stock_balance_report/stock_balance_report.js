

frappe.query_reports["Stock Balance Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			width: "80",
			options: "Company",
			default: frappe.defaults.get_default("company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			default: frappe.datetime.get_today(),
		},
		{
    fieldname: "item_group",
    label: __("Item Group"),
    fieldtype: "MultiSelectList",
    width: "80",
    options: "Item Group",
    get_data: async function (txt) {
        let { message: data } = await frappe.call({
            method: "frappe.desk.search.search_link",
            args: {
                doctype: "Item Group",
                txt: txt,
                searchfield: "name",
                start: 0,
                page_len: 20,
                filters: {},
            },
        });
        return data;
    },
},

		{
			fieldname: "item_code",
			label: __("Items"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Item",
			get_data: async function (txt) {
	let item_group = frappe.query_report.get_filter_value("item_group");

	let filters = {
		is_stock_item: 1,
	};

	// only include item_group if it's not empty
	if (item_group && item_group.length > 0) {
		filters["item_group"] = ["in", item_group];
	}

	let { message: data } = await frappe.call({
		method: "erpnext.controllers.queries.item_query",
		args: {
			doctype: "Item",
			txt: txt,
			searchfield: "name",
			start: 0,
			page_len: 10,
			filters: filters,
			as_dict: 1,
		},
	});

	return (data || []).map(d => ({
            value: d.name,             // actual value stored
            description: d.item_name 
             }));
},
},

		{
			fieldname: "warehouse",
			label: __("Warehouses"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Warehouse",
			get_data: (txt) => {
				let warehouse_type = frappe.query_report.get_filter_value("warehouse_type");
				let company = frappe.query_report.get_filter_value("company");

				let filters = {
					...(warehouse_type && { warehouse_type }),
					...(company && { company }),
				};

				return frappe.db.get_link_options("Warehouse", txt, filters);
			},
		},
		{
			fieldname: "warehouse_type",
			label: __("Warehouse Type"),
			fieldtype: "Link",
			width: "80",
			options: "Warehouse Type",
		},
		{
			fieldname: "valuation_field_type",
			label: __("Valuation Field Type"),
			fieldtype: "Select",
			width: "80",
			options: "Currency\nFloat",
			default: "Currency",
		},
		{
			fieldname: "include_uom",
			label: __("Include UOM"),
			fieldtype: "Link",
			options: "UOM",
		},
		{
			fieldname: "show_variant_attributes",
			label: __("Show Variant Attributes"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_stock_ageing_data",
			label: __("Show Stock Ageing Data"),
			fieldtype: "Check",
		},
		{
			fieldname: "ignore_closing_balance",
			label: __("Ignore Closing Balance"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "include_zero_stock_items",
			label: __("Include Zero Stock Items"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_dimension_wise_stock",
			label: __("Show Dimension Wise Stock"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "out_qty" && data && data.out_qty > 0) {
			value = "<span style='color:red'>" + value + "</span>";
		} else if (column.fieldname == "in_qty" && data && data.in_qty > 0) {
			value = "<span style='color:green'>" + value + "</span>";
		}

		return value;
	},
};

erpnext.utils.add_inventory_dimensions("Stock Balance", 8);
