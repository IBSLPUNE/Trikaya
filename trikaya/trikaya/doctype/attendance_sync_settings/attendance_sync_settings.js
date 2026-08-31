frappe.ui.form.on("Attendance Sync Settings", {
	refresh: function (frm) {
		frm.add_custom_button(__("Sync Now"), function () {
			frappe.call({
				method: "trikaya.trikaya.sync.sync_now",
				freeze: true,
				freeze_message: __("Syncing attendance..."),
				callback: function (r) {
					frm.reload_doc();
					if (r.message) {
						frappe.msgprint(r.message);
					}
				},
			});
		});
	},
});
