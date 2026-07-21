# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

"""Purchase Invoice price differences for SAP-MA items (doc_event on_submit).

When a PI bills a routed Purchase Receipt at a different price, the receipt's
SLEs are never touched (core's adjust-incoming-rate/repost flow is disabled
for routed items). Instead the difference posts as a current-dated
``invoice_diff`` valuation event:

- functional currency: the whole difference splits by Stock Ratio
  (inventory portion -> Stock In Hand + MAP recalc; rest -> Price Difference).
- foreign currency (IFRS): the price component is measured at the RECEIPT
  exchange rate and splits by Stock Ratio; the residual FX movement goes to
  Exchange Gain/Loss and never touches inventory.

The GL offset is Stock Received But Not Billed: the kernel credited SRBNB at
receipt value, the PI debits it at billed value — this event clears exactly
the residue.
"""

import frappe
from frappe.utils import flt

from sap_valuation.sap_moving_average.kernel import get_stock_ratio, post_value_event


def on_purchase_invoice_submit(doc, method=None):
	if doc.get("is_return") or doc.get("update_stock") or doc.get("is_cancellation"):
		return
	kernel_map = frappe.get_hooks("sap_valuation_kernels")
	if not kernel_map:
		return

	from erpnext.stock.utils import get_valuation_method

	company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")
	srbnb = frappe.get_cached_value("Company", doc.company, "stock_received_but_not_billed")

	for item in doc.items:
		if not (item.purchase_receipt and item.pr_detail):
			continue
		method = get_valuation_method(item.item_code, doc.company)
		if method not in kernel_map:
			continue

		pr_row = frappe.db.get_value(
			"Purchase Receipt Item",
			item.pr_detail,
			["net_rate", "base_net_rate", "warehouse"],
			as_dict=True,
		)
		if not pr_row:
			continue

		if method == "SAP Standard Cost":
			from sap_valuation.sap_standard_cost.kernel import on_purchase_invoice_submit_std

			on_purchase_invoice_submit_std(doc, item, pr_row)
			continue

		qty = flt(item.qty)
		base_diff = flt((flt(item.base_net_rate) - flt(pr_row.base_net_rate)) * qty, 2)
		if not base_diff:
			continue

		fx_variance = 0.0
		inventory_component = base_diff
		if doc.currency != company_currency:
			receipt_fx = flt(
				frappe.db.get_value("Purchase Receipt", item.purchase_receipt, "conversion_rate")
			)
			unit_diff_foreign = flt(item.net_rate) - flt(pr_row.net_rate)
			inventory_component = flt(unit_diff_foreign * qty * receipt_fx, 2)
			fx_variance = flt(base_diff - inventory_component, 2)

		ratio = get_stock_ratio(doc.company, item.item_code, pr_row.warehouse)
		inventory_portion = flt(inventory_component * ratio, 2)
		expense_portion = flt(inventory_component - inventory_portion, 2)

		post_value_event(
			doc.company,
			item.item_code,
			pr_row.warehouse,
			source=("Purchase Invoice", doc.name, item.name),
			posting_date=doc.posting_date,
			reason="invoice_diff" if not fx_variance else "fx_adjust",
			value_delta=inventory_portion,
			expense_portion=expense_portion,
			fx_variance=fx_variance,
			offset_account=srbnb,
		)
