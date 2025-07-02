# trikaya/overrides/doctype/sales_order/sales_order.py
import frappe
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder as _SalesOrder

class SalesOrder(_SalesOrder):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from erpnext.accounts.doctype.payment_schedule.payment_schedule import PaymentSchedule
        from erpnext.accounts.doctype.pricing_rule_detail.pricing_rule_detail import PricingRuleDetail
        from erpnext.accounts.doctype.sales_taxes_and_charges.sales_taxes_and_charges import SalesTaxesandCharges
        from erpnext.selling.doctype.sales_order_item.sales_order_item import SalesOrderItem
        from erpnext.selling.doctype.sales_team.sales_team import SalesTeam
        from erpnext.stock.doctype.packed_item.packed_item import PackedItem
        from frappe.types import DF

        additional_discount_percentage: DF.Float
        address_display: DF.SmallText | None
        advance_paid: DF.Currency
        amended_from: DF.Link | None
        amount_eligible_for_commission: DF.Currency
        apply_discount_on: DF.Literal["", "Grand Total", "Net Total"]
        auto_repeat: DF.Link | None
        base_discount_amount: DF.Currency
        base_grand_total: DF.Currency
        base_in_words: DF.Data | None
        base_net_total: DF.Currency
        base_rounded_total: DF.Currency
        base_rounding_adjustment: DF.Currency
        base_total: DF.Currency
        base_total_taxes_and_charges: DF.Currency
        billing_status: DF.Literal["Not Billed", "Fully Billed", "Partly Billed", "Closed"]
        campaign: DF.Link | None
        commission_rate: DF.Float
        company: DF.Link
        company_address: DF.Link | None
        company_address_display: DF.SmallText | None
        company_contact_person: DF.Link | None
        contact_display: DF.SmallText | None
        contact_email: DF.Data | None
        contact_mobile: DF.SmallText | None
        contact_person: DF.Link | None
        contact_phone: DF.Data | None
        conversion_rate: DF.Float
        cost_center: DF.Link | None
        coupon_code: DF.Link | None
        currency: DF.Link
        customer: DF.Link
        customer_address: DF.Link | None
        customer_group: DF.Link | None
        customer_name: DF.Data | None
        delivery_date: DF.Date | None
        delivery_status: DF.Literal["Not Delivered", "Fully Delivered", "Partly Delivered", "Closed", "Not Applicable"]
        disable_rounded_total: DF.Check
        discount_amount: DF.Currency
        dispatch_address: DF.SmallText | None
        dispatch_address_name: DF.Link | None
        from_date: DF.Date | None
        grand_total: DF.Currency
        group_same_items: DF.Check
        has_unit_price_items: DF.Check
        ignore_pricing_rule: DF.Check
        in_words: DF.Data | None
        incoterm: DF.Link | None
        inter_company_order_reference: DF.Link | None
        is_internal_customer: DF.Check
        items: DF.Table[SalesOrderItem]
        language: DF.Data | None
        letter_head: DF.Link | None
        loyalty_amount: DF.Currency
        loyalty_points: DF.Int
        named_place: DF.Data | None
        naming_series: DF.Literal["SAL-ORD-.YYYY.-"]
        net_total: DF.Currency
        order_type: DF.Literal["", "Sales", "Maintenance", "Shopping Cart"]
        other_charges_calculation: DF.TextEditor | None
        packed_items: DF.Table[PackedItem]
        party_account_currency: DF.Link | None
        payment_schedule: DF.Table[PaymentSchedule]
        payment_terms_template: DF.Link | None
        per_billed: DF.Percent
        per_delivered: DF.Percent
        per_picked: DF.Percent
        plc_conversion_rate: DF.Float
        po_date: DF.Date | None
        po_no: DF.Data | None
        price_list_currency: DF.Link
        pricing_rules: DF.Table[PricingRuleDetail]
        project: DF.Link | None
        represents_company: DF.Link | None
        reserve_stock: DF.Check
        rounded_total: DF.Currency
        rounding_adjustment: DF.Currency
        sales_partner: DF.Link | None
        sales_team: DF.Table[SalesTeam]
        scan_barcode: DF.Data | None
        select_print_heading: DF.Link | None
        selling_price_list: DF.Link
        set_warehouse: DF.Link | None
        shipping_address: DF.SmallText | None
        shipping_address_name: DF.Link | None
        shipping_rule: DF.Link | None
        skip_delivery_note: DF.Check
        source: DF.Link | None
        status: DF.Literal["", "Draft", "On Hold", "To Deliver and Bill", "To Bill", "To Deliver", "Completed", "Cancelled", "Closed"]
        tax_category: DF.Link | None
        tax_id: DF.Data | None
        taxes: DF.Table[SalesTaxesandCharges]
        taxes_and_charges: DF.Link | None
        tc_name: DF.Link | None
        terms: DF.TextEditor | None
        territory: DF.Link | None
        title: DF.Data | None
        to_date: DF.Date | None
        total: DF.Currency
        total_commission: DF.Currency
        total_net_weight: DF.Float
        total_qty: DF.Float
        total_taxes_and_charges: DF.Currency
        transaction_date: DF.Date
    # end: auto-generated types
    def autoname(self):
        """
        If `custom_previous_sales_order` is set, force name to "<base>-1";
        otherwise, fall back to the standard naming series.
        """
        origin = getattr(self, "custom_previous_sales_order", None)
        if origin:
            # Replace "/" with "-" so the DB and router accept it
            base = origin.replace("/", "-")
            self.name = f"{base}-1"
            return

        # Otherwise use the standard series or naming rule
        super().autoname()