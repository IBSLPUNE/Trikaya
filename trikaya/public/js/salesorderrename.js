// File: trikaya/trikaya/public/js/sales_order.js
frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        if (frm.doc.docstatus !== 1) return;

        frm.add_custom_button(__('Amend'), async () => {
            // Freeze UI to prevent duplicate clicks
            frappe.dom.freeze(__('Creating duplicate…'));

            try {
                // Call your app’s duplication API
                const { new_name } = await frappe.xcall(
                    'trikaya.customizations.salesrename.duplicate_sales_order',
                    { source_name: frm.doc.name }
                );

                if (new_name) {
                    // Navigate to the new draft
                    frappe.set_route('Form', 'Sales Order', new_name);
                } else {
                    frappe.msgprint({
                        title: __('Duplication Incomplete'),
                        message: __('Server did not return a new_name.'),
                        indicator: 'orange'
                    });
                }
            } catch (err) {
                // Surface real errors only
                const msg = (err.exc || err.message || '').split('\n')[0] 
                            || __('Unknown error');
                frappe.msgprint({
                    title: __('Duplication Failed'),
                    message: msg,
                    indicator: 'red'
                });
                console.error('Amend Error:', err);
            } finally {
                frappe.dom.unfreeze();
            }
        }).addClass('btn-primary');
    }
});
