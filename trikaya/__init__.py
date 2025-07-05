# # File: trikaya/__init__.py

# import frappe
# from frappe.model import naming

# # Keep reference to original function
# _original_get_series = naming.get_naming_series_for_doc

# def _patched_get_series(doctype, doc, meta=None):
#     # If this is a clone (custom_previous_sales_order set), skip rules
#     if doctype == "Sales Order" and getattr(doc, "custom_previous_sales_order", None):
#         return None
#     # Otherwise, use the standard series lookup
#     return _original_get_series(doctype, doc, meta)

# # Override the function in the naming module
# naming.get_naming_series_for_doc = _patched_get_series
__version__ = "0.0.2"
