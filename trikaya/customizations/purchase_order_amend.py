import re
import frappe
from frappe import _
from frappe.utils import now

LOG = frappe.logger("po_amend", allow_site=True, file_count=5)

# -----------------------
# Helpers
# -----------------------
def _strip_suffix(name: str) -> tuple[str, int | None]:
    """Split name into (base, suffix_int_or_None). E.g. 'ABC-3' -> ('ABC', 3), 'ABC' -> ('ABC', None)"""
    m = re.match(r"^(.*?)(?:-(\d+))?$", name)
    if not m:
        return name, None
    base = m.group(1) or name
    suf = int(m.group(2)) if m.group(2) else None
    return base, suf

def _base_for_new_clone(src) -> str:
    """
    Decide the fixed base for amendments:
    - If current doc has custom_previous_purchase_order set -> use that (the original id)
    - Else -> use current name (first amendment from the original)
    """
    prev = (src.get("custom_previous_purchase_order") or "").strip()
    return prev if prev else src.name

def _next_from_base(base: str) -> str:
    """
    Return the next free name from a fixed base using -n suffix:
    base-1, base-2, ...
    """
    # Ensure we don't treat 'base-10' as matching 'base-1' incorrectly; just loop small integers
    n = 1
    while True:
        candidate = f"{base}-{n}"
        if not frappe.db.exists("Purchase Order", candidate):
            return candidate
        n += 1

def _close_original(src_name: str):
    """Mark original PO as Closed + workflow_state Closed and bump modified timestamp."""
    frappe.db.set_value(
        "Purchase Order",
        src_name,
        {"status": "Closed", "workflow_state": "Closed", "modified": now()},
    )
    frappe.db.commit()
    LOG.info(f"[CLOSED] {src_name}")

def _prep_clone(src, fixed_base: str):
    """
    Return a clean Draft clone, reset volatile fields, and set custom_previous_purchase_order
    to the fixed base (the original PO id).
    """
    clone = frappe.copy_doc(src)
    clone.docstatus = 0

    # reset fields
    for f in (
        "workflow_state", "status",
        "per_received", "per_billed",
        "per_installed", "per_returned", "per_delivered"
    ):
        if f in clone.as_dict():
            setattr(clone, f, None)

    if "workflow_state" in clone.as_dict():
        clone.workflow_state = "draft"

    # ensure the draft remembers the original PO id
    clone.set("custom_previous_purchase_order", fixed_base)

    return clone

def _force_rename_po(old_name: str, target_base: str) -> str:
    """
    Force rename a PO draft to target_base-<n>, retrying until a free one is found.
    """
    n = 1
    while True:
        candidate = f"{target_base}-{n}"
        if not frappe.db.exists("Purchase Order", candidate):
            break
        n += 1
    if old_name != candidate:
        LOG.info(f"[RENAME] {old_name} -> {candidate}")
        frappe.rename_doc("Purchase Order", old_name, candidate, force=True, merge=False)
    return candidate

# -----------------------
# Regular flow
# -----------------------
def _amend_regular(src):
    fixed_base = _base_for_new_clone(src)  # original id (from custom_previous_purchase_order) or current
    LOG.info(f"[REGULAR] base={fixed_base}")

    _close_original(src.name)

    clone = _prep_clone(src, fixed_base)

    # Insert first, then rename to fixed_base-<n>
    clone.insert(ignore_permissions=True)
    LOG.info(f"[INSERT] regular clone as {clone.name}")

    target = _next_from_base(fixed_base)
    if clone.name != target:
        frappe.rename_doc("Purchase Order", clone.name, target, force=True, merge=False)
        clone_name = target
    else:
        clone_name = clone.name

    frappe.db.commit()
    return clone_name

# -----------------------
# Subcontracted flow (bullet-proof)
# -----------------------
def _amend_subcontracted(src):
    fixed_base = _base_for_new_clone(src)
    LOG.info(f"[SUBCON] base={fixed_base}")

    _close_original(src.name)

    # Prepare draft, ensure series does not interfere
    clone = _prep_clone(src, fixed_base)
    for f in ("naming_series", "series_value"):
        if f in clone.as_dict():
            try:
                setattr(clone, f, None)
            except Exception:
                pass

    # Set desired target BEFORE insert to try to bypass series
    desired = _next_from_base(fixed_base)
    clone.name = desired
    clone.flags.name_set = True
    clone.flags.name_set_from_naming_series = True

    clone.insert(ignore_permissions=True)
    LOG.info(f"[INSERT] subcon clone as {clone.name}, desired {desired}")

    # If something still changed it, FORCE rename to fixed_base-<n>
    if clone.name != desired:
        desired = _force_rename_po(clone.name, fixed_base)
        LOG.info(f"[FORCED] subcon final {desired}")

    frappe.db.commit()
    return desired

# -----------------------
# Smart endpoint (call this)
# -----------------------
@frappe.whitelist()
def amend_po_smart(po_name: str):
    """
    Smart amend:
    - Store original id into custom_previous_purchase_order on the draft
    - Name the draft strictly as <original_id>-<n>
    - Handles subcontracted and regular cases automatically
    """
    src = frappe.get_doc("Purchase Order", po_name)

    # Allow on anything except true Draft
    if src.docstatus == 0 and (src.workflow_state or "").lower() == "draft":
        frappe.throw(_("Amend is not allowed on Draft."))

    is_sub = bool(src.get("is_subcontracted"))
    LOG.info(f"[BEGIN] {src.name} (sub={is_sub})")

    # If the source already has custom_previous_purchase_order, keep using that as base.
    # Otherwise, set the base to the current src.name (first amendment).
    # The clone will always have custom_previous_purchase_order = fixed base.
    if is_sub:
        new_name = _amend_subcontracted(src)
    else:
        new_name = _amend_regular(src)

    LOG.info(f"[DONE] new draft {new_name}")
    return new_name
