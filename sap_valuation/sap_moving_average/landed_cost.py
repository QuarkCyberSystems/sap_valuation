# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

"""Landed Cost Voucher handling for SAP-MA items (``sap_valuation_landed_cost`` hook).

Core's LCV retroactively revalues the receipt's SLEs in place. For kernel
items the charge instead posts as a current-dated ``landed_cost`` valuation
event split by the Stock Ratio (inventory portion -> Stock In Hand + MAP
recalc; consumed portion -> Price Difference).

Returns True when the voucher was fully handled (all items routed), False
when no item is routed (core proceeds). Mixed vouchers are rejected — split
the LCV so kernel and core items don't share one in-place revaluation.
"""

import frappe
from frappe import _
from frappe.utils import flt

from sap_valuation.sap_moving_average.kernel import get_stock_ratio, post_value_event
from sap_valuation.shared.accounts import get_offset_account


def handle_landed_cost(lcv):
	from erpnext.stock.utils import get_valuation_method

	kernel_map = frappe.get_hooks("sap_valuation_kernels")
	items = lcv.get("items") or []
	if not items or not kernel_map:
		return False

	methods = {row.name: get_valuation_method(row.item_code, lcv.company) for row in items}
	routed = [row for row in items if methods[row.name] in kernel_map]
	if not routed:
		return False
	if len(routed) != len(items):
		frappe.throw(
			_(
				"This Landed Cost Voucher mixes SAP-valuation items with conventionally valued "
				"items. Split it into separate vouchers per valuation family."
			),
			title=_("Mixed Valuation Voucher"),
		)

	if lcv.docstatus == 2:
		frappe.throw(
			_("Landed Cost Vouchers for SAP-valuation items cannot be cancelled. Use Create Cancellation."),
			title=_("Immutable Ledger"),
		)

	std_rows = [row for row in routed if methods[row.name] == "SAP Standard Cost"]
	if std_rows:
		from sap_valuation.sap_standard_cost.kernel import handle_std_landed_cost

		handle_std_landed_cost(lcv, std_rows)
	routed = [row for row in routed if methods[row.name] != "SAP Standard Cost"]

	# proportional credit against each charge row's expense account
	total_charges = sum(flt(t.base_amount or t.amount) for t in lcv.get("taxes") or [])
	for row in routed:
		amount = flt(row.applicable_charges)
		if not amount:
			continue
		warehouse = frappe.db.get_value(
			row.receipt_document_type + " Item", row.purchase_receipt_item, "warehouse"
		) if row.get("purchase_receipt_item") else None

		ratio = get_stock_ratio(lcv.company, row.item_code, warehouse)
		inventory_portion = flt(amount * ratio, 2)
		expense_portion = flt(amount - inventory_portion, 2)

		for tax in lcv.get("taxes") or []:
			share = flt(tax.base_amount or tax.amount) / total_charges if total_charges else 0
			if not share:
				continue
			post_value_event(
				lcv.company,
				row.item_code,
				warehouse,
				source=("Landed Cost Voucher", lcv.name, row.name),
				posting_date=lcv.posting_date,
				reason="landed_cost",
				value_delta=flt(inventory_portion * share, 2),
				expense_portion=flt(expense_portion * share, 2),
				offset_account=tax.expense_account,
			)
	return True
