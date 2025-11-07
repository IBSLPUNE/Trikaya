# File: apps/trikaya/trikaya/customizations/purchase_order_amend.py

import re
import frappe
from frappe import _
from frappe.utils import now

LOG = frappe.logger("po_amend", allow_site=True, file_count=5)

# -----------------------
# Small helpers
# -----------------------
def _next_from_base(base: str) -> str:
    n = 1
    while True:
        candidate = f"{base}-{n}"
        if not frappe.db.exists("Purchase Order", candidate):
            return candidate
        n += 1

def _base_for_new_clone(src) -> str:
    prev = (src.get("custom_previous_purchase_order") or "").strip()
    return prev if prev else src.name

def _close_original(src_name: str):
    frappe.db.set_value(
        "Purchase Order",
        src_name,
        {"status": "Closed", "workflow_state": "Closed", "modified": now()},
    )
    frappe.db.commit()
    LOG.info(f"[CLOSED] {src_name}")

def _safe_zero(doc, fields):
    for f in fields:
        if hasattr(doc, f):
            try:
                setattr(doc, f, 0)
            except Exception:
                pass

def _safe_clear(doc, fields):
    for f in fields:
        if hasattr(doc, f):
            try:
                setattr(doc, f, None)
            except Exception:
                pass

def _defensive_clear_fields(doc, substrings):
    """
    Clear any attribute whose fieldname contains any of the substrings (case-insensitive).
    Useful when vendors/patches add new subcontracting link fields.
    """
    d = doc.as_dict() if hasattr(doc, "as_dict") else {}
    for key in list(d.keys()):
        low = key.lower()
        if any(s in low for s in substrings):
            try:
                setattr(doc, key, None)
            except Exception:
                pass

def _prep_clone(src, fixed_base: str):
    """
    Clean Draft clone for a fresh subcontracting cycle:
    - Reset volatile header fields
    - Remember original id in custom_previous_purchase_order
    - Zero/clear child rows so no progress/link remains
    """
    clone = frappe.copy_doc(src)
    clone.docstatus = 0

    # ---------- header resets ----------
    header_zero_fields = [
        "per_received", "per_billed", "per_installed",
        "per_returned", "per_delivered", "per_subcontracted"  # <- important if present
    ]
    _safe_zero(clone, header_zero_fields)

    header_clear_fields = ["workflow_state", "status"]
    _safe_clear(clone, header_clear_fields)

    if "workflow_state" in clone.as_dict():
        clone.workflow_state = "draft"

    # keep strict naming base
    clone.set("custom_previous_purchase_order", fixed_base)

    # ---------- item resets ----------
    item_zero_fields = [
        "received_qty",
        "billed_qty",
        "billed_amt",
        "delivered_by_supplier",
        "subcontracted_qty",   # <- critical
        "supplied_qty",
        "returned_qty",
        # DO NOT zero 'qty' (ordered qty) – leave user's intended qty intact
    ]
    item_clear_fields = [
        # links to prior docs
        "purchase_receipt", "pr_detail",
        "prevdoc_docname", "prevdoc_detail_docname",
        "prevdoc_doctype", "material_request", "material_request_item",
        "subcontracting_order", "subcontracting_order_item",
        "subcontracting_order_supplied_item",
    ]

    # defensive patterns to clear any unknown vendor fields
    item_defensive_substrings = [
        "subcontract", "supplied", "reference", "purchase_receipt", "stock_entry",
        "stock_entry_detail", "linked_", "prevdoc"
    ]

    for it in (clone.items or []):
        _safe_zero(it, item_zero_fields)
        _safe_clear(it, item_clear_fields)
        _defensive_clear_fields(it, item_defensive_substrings)

    # ---------- supplied items table (if exists) ----------
    supplied_zero_fields = ["consumed_qty", "supplied_qty", "returned_qty"]
    supplied_clear_fields = [
        "reference_doctype", "reference_name", "reference_row",
        "purchase_receipt", "stock_entry", "stock_entry_detail",
        "subcontracting_order", "subcontracting_order_item",
    ]
    supplied_defensive_substrings = [
        "subcontract", "supplied", "reference", "purchase_receipt",
        "stock_entry", "linked_", "prevdoc"
    ]

    if hasattr(clone, "supplied_items"):
        for si in (clone.supplied_items or []):
            _safe_zero(si, supplied_zero_fields)
            _safe_clear(si, supplied_clear_fields)
            _defensive_clear_fields(si, supplied_defensive_substrings)

    return clone

def _force_rename_po(old_name: str, target_base: str) -> str:
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
    fixed_base = _base_for_new_clone(src)
    LOG.info(f"[REGULAR] base={fixed_base}")

    _close_original(src.name)

    clone = _prep_clone(src, fixed_base)

    # Insert first (temp name), then rename to strict base-n
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
# Subcontracted flow (strict naming)
# -----------------------
def _amend_subcontracted(src):
    fixed_base = _base_for_new_clone(src)
    LOG.info(f"[SUBCON] base={fixed_base}")

    _close_original(src.name)

    clone = _prep_clone(src, fixed_base)

    # reduce series interference
    for f in ("naming_series", "series_value"):
        if f in clone.as_dict():
            try:
                setattr(clone, f, None)
            except Exception:
                pass

    # set desired name BEFORE insert to try bypassing series
    desired = _next_from_base(fixed_base)
    clone.name = desired
    clone.flags.name_set = True
    clone.flags.name_set_from_naming_series = True

    clone.insert(ignore_permissions=True)
    LOG.info(f"[INSERT] subcon clone as {clone.name}, desired {desired}")

    # if series or hooks changed it, force rename
    if clone.name != desired:
        desired = _force_rename_po(clone.name, fixed_base)
        LOG.info(f"[FORCED] subcon final {desired}")

    frappe.db.commit()
    return desired

# -----------------------
# Smart endpoint (call from client)
# -----------------------
@frappe.whitelist()
def amend_po_smart(po_name: str):
    """
    Smart amend that:
    - Closes original PO (status/workflow_state -> Closed)
    - Creates clean Draft clone
    - Ensures custom_previous_purchase_order = original id
    - Strictly names clone as <original>-n
    - Resets all subcontracting progress/links so "fully subcontracted" never triggers
    - Returns new draft name
    """
    src = frappe.get_doc("Purchase Order", po_name)

    # Block only true Draft
    if src.docstatus == 0 and (src.workflow_state or "").lower() == "draft":
        frappe.throw(_("Amend is not allowed on Draft."))

    is_sub = bool(src.get("is_subcontracted"))
    LOG.info(f"[BEGIN] Amend {src.name} (is_subcontracted={is_sub})")

    if is_sub:
        new_name = _amend_subcontracted(src)
    else:
        new_name = _amend_regular(src)

    LOG.info(f"[DONE] New draft {new_name}")
    return new_name
