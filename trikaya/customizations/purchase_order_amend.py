import re
import frappe
from frappe import _
from frappe.utils import now

def _next_clone_name(src_name: str) -> str:
    """Return src_name-<n> where n is the next available integer, supporting slashes."""
    m = re.match(r"^(.*?)(?:-(\d+))?$", src_name)
    base = m.group(1) if m else src_name
    n = int(m.group(2)) + 1 if (m and m.group(2)) else 1

    # loop until a free name is found
    while frappe.db.exists("Purchase Order", f"{base}-{n}"):
        n += 1
    return f"{base}-{n}"

@frappe.whitelist()
def amend_po(po_name: str):
    """
    Close the current PO (without cancel), duplicate to a new Draft with incremented -N suffix.
    Shows up on all states except true Draft.
    """
    src = frappe.get_doc("Purchase Order", po_name)

    # Block only true draft (UI hides, but keep server-guard)
    if src.docstatus == 0 and (src.workflow_state or "").lower() == "draft":
        frappe.throw(_("Amend is not allowed on Draft."))

    # 1) Mark original as Closed (keep its docstatus) AND set workflow_state to Closed
    #    Also bump the modified timestamp so list view / caches reflect the change immediately.
    frappe.db.set_value("Purchase Order", src.name, {
        "status": "Closed",
        "workflow_state": "Closed",
        "modified": now()
    })

    # commit so list queries see the updated state before clone is inserted
    frappe.db.commit()

    # 2) Make clean draft copy (do NOT set amended_from)
    clone = frappe.copy_doc(src)
    clone.docstatus = 0

    # reset fields that should start fresh
    for f in ("workflow_state", "status", "per_received", "per_billed",
              "per_installed", "per_returned", "per_delivered"):
        if f in clone.as_dict():
            setattr(clone, f, None)

    # (Optional) force workflow_state to 'draft' if your workflow uses that exact label
    if "workflow_state" in clone.as_dict():
        clone.workflow_state = "draft"

    # 3) Insert first (get a temp name safely)
    clone.insert(ignore_permissions=True)

    # 4) Compute target name and rename with collision handling
    target = _next_clone_name(src.name)
    if clone.name != target:
        frappe.rename_doc("Purchase Order", clone.name, target, force=True, merge=False)

    frappe.db.commit()
    return target
