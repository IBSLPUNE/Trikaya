import frappe

@frappe.whitelist()
def duplicate_sales_order(source_name):
    """
    1) Clone a submitted SO into a draft
    2) Insert it so all standard hooks run
    3) Rename it to '<base>-1' with force=True
    4) Return the final name
    """
    # 1) Fetch & guard
    src = frappe.get_doc("Sales Order", source_name)
    if src.docstatus != 1:
        frappe.throw("Only submitted Sales Orders may be duplicated")

    # 2) Deep copy (including items, taxes, etc.)
    new_so = frappe.copy_doc(src, ignore_no_copy=False)
    new_so.docstatus = 0
    new_so.amended_from = None
    new_so.custom_previous_sales_order = source_name

    # 3) Insert the draft (Naming Rule still applies here)
    new_so.insert(ignore_permissions=True)

    # 4) Compute a safe base and target name
    base   = source_name.replace("/", "-")       # avoid slash in name
    target = f"{base}-1"

    # 5) Rename the document at the DB level, force‐bypassing any naming logic
    frappe.rename_doc(
        doctype="Sales Order",
        old=new_so.name,
        new=target,
        force=True              # allow rename even if normally disallowed
    )

    # 6) Return for client routing
    return {"new_name": target}
