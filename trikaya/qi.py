import frappe

@frappe.whitelist()
def force_create_quality_inspection(reference_type, reference_name, item_code):
    # 1. Only for submitted POs/PRs
    doc = frappe.get_doc(reference_type, reference_name)
    if doc.docstatus != 1:
        frappe.throw("Quality Inspection can only be created for submitted documents.")

    # 2. Build a new QI in DRAFT, bypassing its validate() on save
    qi = frappe.new_doc("Quality Inspection")
    qi.flags.ignore_validate = True   # <— skip the inspection_required check here
    qi.item_code         = item_code
    qi.inspection_type   = "Incoming"
    qi.reference_type    = reference_type
    qi.reference_name    = reference_name
    qi.report_date       = frappe.utils.nowdate()
    qi.inspected_by      = frappe.session.user
    qi.sample_size      = 1

    qi.save(ignore_permissions=True)
    return qi.name
# in ganesh/api.py



def bypass_inspection_required(doc, method):
    """
    Skip ERPNext's 'inspection_required' check
    when saving or submitting a QI for our exempted SKU.
    """
    if doc.item_code == "T01010F0490N":
        # this flag silences the "Inspection Required..." throw
        doc.flags.ignore_validate = True
