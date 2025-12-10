import frappe

def create_bank_account_for_supplier(doc, method):
    """
    After creation of Supplier, create Bank Account with only 4 fields.
    """

    # Ensure required fields exist
    if not (doc.custom_bank and doc.custom_bank_account_no and doc.custom_ifsc_code):
        return

    # Avoid duplicate bank account
    if frappe.db.exists("Bank Account", {"bank_account_no": doc.custom_bank_account_no}):
        return

    bank_account = frappe.get_doc({
        "doctype": "Bank Account",
        "account_name": doc.supplier_name,
        "bank": doc.custom_bank,
        "bank_account_no": doc.custom_bank_account_no,
        "custom_ifsc_code": doc.custom_ifsc_code
    })

    bank_account.insert(ignore_permissions=True)
