import re
import frappe
from frappe import _
from frappe.utils import now

LOG = frappe.logger("po_amend", allow_site=True, file_count=5)

# ============================================
# Helpers
# ============================================

def _next_from_base(base: str) -> str:
    """
    Returns the next available name for a given base.
    e.g. base = "100" -> "100-1", then "100-2", etc.
    """
    n = 1
    while True:
        name = f"{base}-{n}"
        if not frappe.db.exists("Purchase Order", name):
            return name
        n += 1


def _base_for_new_clone(src):
    """
    Compute the ORIGINAL base purely from name:

    - "100"      -> base "100"
    - "100-1"    -> base "100"
    - "100-2"    -> base "100"
    - "PO-0001"  -> base "PO-0001"
    - "PO-0001-1"-> base "PO-0001"

    We do NOT use custom_previous_purchase_order as base anymore.
    That field is now "immediate previous PO".
    """
    name = src.name or ""
    m = re.match(r"^(.*)-(\d+)$", name)
    if m:
        # prefix before the last "-<number>"
        return m.group(1)
    return name


def _close_original(src_name: str):
    """
    Close the original PO.
    (Amendability is derived from name chain, not a flag field.)
    """
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
    d = doc.as_dict()
    for key in d:
        low = key.lower()
        if any(s in low for s in substrings):
            try:
                setattr(doc, key, None)
            except Exception:
                pass

# ============================================
# Clone cleaner (critical for subcontracting)
# ============================================

def _prep_clone(src, base: str):
    """
    Prepare cloned doc:
    - Reset percent / linkage fields
    - Set custom_previous_purchase_order = IMMEDIATE previous PO (src.name)
    """
    clone = frappe.copy_doc(src)
    clone.docstatus = 0

    # --- Header resets ---
    _safe_zero(clone, [
        "per_received", "per_billed", "per_installed", "per_returned",
        "per_delivered", "per_subcontracted"
    ])
    _safe_clear(clone, ["workflow_state", "status"])
    clone.workflow_state = "draft"

    # ------------------------------
    # THIS IS THE IMPORTANT CHANGE:
    # previous purchase order = current source name
    # ------------------------------
    clone.custom_previous_purchase_order = src.name

    # --- Item resets ---
    item_zero_fields = [
        "received_qty", "billed_qty", "billed_amt",
        "delivered_by_supplier", "subcontracted_qty",
        "supplied_qty", "returned_qty"
    ]
    item_clear_fields = [
        "purchase_receipt", "pr_detail",
        "prevdoc_docname", "prevdoc_detail_docname",
        "prevdoc_doctype", "material_request", "material_request_item",
        "subcontracting_order", "subcontracting_order_item",
        "subcontracting_order_supplied_item"
    ]
    defensive_item = [
        "subcontract", "supplied", "reference",
        "purchase_receipt", "stock_entry", "prevdoc"
    ]

    for it in clone.items:
        _safe_zero(it, item_zero_fields)
        _safe_clear(it, item_clear_fields)
        _defensive_clear_fields(it, defensive_item)

    # --- Supplied Items ---
    supplied_zero = ["consumed_qty", "supplied_qty", "returned_qty"]
    supplied_clear = [
        "reference_doctype", "reference_name", "reference_row",
        "purchase_receipt", "stock_entry", "stock_entry_detail",
        "subcontracting_order", "subcontracting_order_item"
    ]
    defensive_sup = ["subcontract", "supplied", "purchase_receipt", "stock_entry"]

    if hasattr(clone, "supplied_items"):
        for si in clone.supplied_items:
            _safe_zero(si, supplied_zero)
            _safe_clear(si, supplied_clear)
            _defensive_clear_fields(si, defensive_sup)

    return clone

# ============================================
# Renamer
# ============================================

def _force_rename_po(old_name: str, base: str) -> str:
    n = 1
    while True:
        target = f"{base}-{n}"
        if not frappe.db.exists("Purchase Order", target):
            break
        n += 1
    if target != old_name:
        frappe.rename_doc("Purchase Order", old_name, target, force=True, merge=False)
    return target

# ============================================
# Chain / latest logic
# ============================================

def _parse_index(name: str, base: str) -> int:
    """
    base      -> index 0
    base-1    -> index 1
    base-10   -> index 10
    anything else -> 0 (safe)
    """
    if name == base:
        return 0
    prefix = base + "-"
    if name.startswith(prefix):
        tail = name[len(prefix):]
        try:
            return int(tail)
        except Exception:
            return 0
    return 0


def _is_latest_in_chain(po) -> bool:
    """
    Only the latest PO in the chain (by numeric suffix) is amendable.
    Chain is defined by base (derived from name).
    """
    base = _base_for_new_clone(po)

    # all POs whose name is base-* (e.g. "100-1", "100-2")
    child_names = frappe.db.get_all(
        "Purchase Order",
        # name LIKE 'base-%'
        filters=[["Purchase Order", "name", "like", f"{base}-%"]],
        pluck="name",
    )

    names = [base] + child_names

    latest = max(names, key=lambda nm: _parse_index(nm, base))
    return latest == po.name


def _can_amend_po_internal(po) -> bool:
    """
    Internal rule:
    - must be submitted
    - not closed
    - must be latest in its chain
    """
    if po.docstatus != 1:
        return False

    status = (po.status or "").lower()
    ws = (po.workflow_state or "").lower()

    if status == "closed" or ws == "closed":
        return False

    # only latest in chain is allowed to amend
    if not _is_latest_in_chain(po):
        return False

    return True

# ============================================
# REGULAR AMEND
# ============================================

def _amend_regular(src):
    base = _base_for_new_clone(src)  # always ends up like "100"
    LOG.info(f"[REGULAR] base={base}")

    # close old
    _close_original(src.name)

    # prepare clone (previous PO id = src.name)
    clone = _prep_clone(src, base)
    clone.insert(ignore_permissions=True)

    # strict final rename
    target = _next_from_base(base)  # 100-1, then 100-2, 100-3, ...
    if clone.name != target:
        frappe.rename_doc("Purchase Order", clone.name, target, force=True)

    frappe.db.commit()
    return target

# ============================================
# SUBCONTRACTED AMEND
# ============================================

def _amend_sub(src):
    base = _base_for_new_clone(src)
    LOG.info(f"[SUB] base={base}")

    # close old
    _close_original(src.name)

    clone = _prep_clone(src, base)

    # stop naming series interference
    for f in ("naming_series", "series_value"):
        if hasattr(clone, f):
            setattr(clone, f, None)

    desired = _next_from_base(base)
    clone.name = desired
    clone.flags.name_set = True

    clone.insert(ignore_permissions=True)

    # if series still overrode
    if clone.name != desired:
        desired = _force_rename_po(clone.name, base)

    frappe.db.commit()
    return desired

# ============================================
# PUBLIC: can_amend_po (used by client)
# ============================================

@frappe.whitelist()
def can_amend_po(po_name: str) -> bool:
    po = frappe.get_doc("Purchase Order", po_name)
    return _can_amend_po_internal(po)

# ============================================
# SMART PUBLIC API
# ============================================

@frappe.whitelist()
def amend_po_smart(po_name: str):
    src = frappe.get_doc("Purchase Order", po_name)

    # 0) Hard block via internal rule (latest + not closed + submitted)
    if not _can_amend_po_internal(src):
        frappe.throw(_("Amend is not allowed on this Purchase Order."))

    # 1) Block true draft (defensive)
    if src.docstatus == 0 and (src.workflow_state or "").lower() == "draft":
        frappe.throw(_("Amend is not allowed on Draft."))

    # 2) Normal routing
    if src.is_subcontracted:
        new_name = _amend_sub(src)
    else:
        new_name = _amend_regular(src)

    LOG.info(f"[DONE] new draft {new_name}")
    return new_name

# ============================================
# AUTOMATIC: When PO is reopened → force APPROVED
# ============================================

def _coerce_approved_badge(po):
    """
    If PO is submitted & not closed → status/workflow_state = Approved
    This ensures list view always shows correct badge.
    """
    if po.docstatus == 1 and (po.status or "").lower() != "closed":
        frappe.db.set_value("Purchase Order", po.name, {
            "status": "Approved",
            "workflow_state": "Approved",
            "modified": now()
        })
        frappe.db.commit()


def ensure_approved_badge_on_reopen(doc, method=None):
    try:
        if doc.doctype != "Purchase Order":
            return
        _coerce_approved_badge(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ensure_approved_badge_on_reopen")
