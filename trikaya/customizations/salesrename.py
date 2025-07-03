import frappe
from frappe import _

@frappe.whitelist()
def duplicate_sales_order(source_name):
    """
    1) Deep-copy a submitted SO into a draft.
    2) Insert it so all child-tables & validations run.
    3) Compute next suffix based on existing clones.
    4) Rename the draft to "<base>-<n>" with force=True.
    5) Return the final name.
    """
    # 1) Fetch & guard
    src = frappe.get_doc("Sales Order", source_name)
    if src.docstatus != 1:
        frappe.throw(_("Only submitted Sales Orders may be duplicated"))

    # 2) Clone into a draft
    new_so = frappe.copy_doc(src, ignore_no_copy=False)
    new_so.docstatus = 0
    new_so.amended_from = None
    new_so.custom_previous_sales_order = source_name
    new_so.insert(ignore_permissions=True)

    # 3) Sanitize base (slashes → dashes)
    base = source_name.replace("/", "-")

    # 4) Determine the next suffix n
    count = frappe.db.count("Sales Order",
        {"custom_previous_sales_order": source_name}
    )
    # build candidate and bump if it already exists
    target = f"{base}-{count}"
    while frappe.db.exists("Sales Order", target):
        count += 1
        target = f"{base}-{count}"

    # 5) Rename at the DB level, bypassing Naming Rules & Allow Rename guard
    try:
        frappe.rename_doc(
            "Sales Order",
            new_so.name,
            target,
            force=True
        )
    except Exception as e:
        frappe.log_error(f"[duplicate_sales_order] rename failed: {e}",
                         "Sales Order Duplication Error")
        frappe.throw(_("Could not rename duplicated Sales Order. Check logs."))

    # 6) Return for client routing
    return {"new_name": target}
