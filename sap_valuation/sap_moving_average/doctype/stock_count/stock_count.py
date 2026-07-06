# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sap_valuation.shared.accounts import get_offset_account
from sap_valuation.shared.routing import SAP_VALUATION_METHODS


class StockCount(Document):
	"""MI07-style physical count for SAP-MA items.

	Client rule: the user enters quantity ONLY; the system values the
	difference at the period MAP. No manual value entry, ever.
	"""

	def validate(self):
		from erpnext.stock.utils import get_valuation_method

		for row in self.items:
			if get_valuation_method(row.item_code, self.company) not in SAP_VALUATION_METHODS:
				frappe.throw(
					_("Row {0}: {1} is not a SAP-valuation item.").format(row.idx, row.item_code)
				)
			self.set_current_state(row)
			row.quantity_difference = flt(flt(row.counted_qty) - flt(row.current_qty), 6)
			row.difference_amount = flt(flt(row.quantity_difference) * flt(row.valuation_rate), 2)

	def set_current_state(self, row):
		include_wh = frappe.get_cached_value("Item", row.item_code, "valuation_includes_warehouse")
		ipb = frappe.get_all(
			"Inventory Period Balance",
			filters={
				"company": self.company,
				"item_code": row.item_code,
				"warehouse": (row.warehouse or "") if include_wh else "",
			},
			fields=["closing_qty", "moving_avg_price", "is_negative", "frozen_map"],
			order_by="period_year desc, period_month desc",
			limit=1,
		)
		row.current_qty = flt(ipb[0].closing_qty) if ipb else 0
		row.valuation_rate = (
			flt(ipb[0].frozen_map) if ipb and ipb[0].is_negative else flt(ipb[0].moving_avg_price)
		) if ipb else 0

	def on_submit(self):
		from sap_valuation.sap_moving_average.kernel import post_value_event

		for row in self.items:
			if not flt(row.quantity_difference):
				continue
			account = row.variance_account or get_offset_account(
				self.company, row.item_code, row.warehouse, "count_diff"
			)
			if not account:
				frappe.throw(
					_("Row {0}: no variance account resolvable for {1}.").format(row.idx, row.item_code)
				)
			post_value_event(
				self.company,
				row.item_code,
				row.warehouse,
				source=(self.doctype, self.name, row.name),
				posting_date=self.posting_date,
				reason="count_diff",
				value_delta=0,  # derived from qty x period MAP inside the kernel
				qty_delta=flt(row.quantity_difference),
				movement_type="count_gain" if flt(row.quantity_difference) > 0 else "count_loss",
				offset_account=account,
			)

	def before_cancel(self):
		frappe.throw(
			_(
				"Stock Count cannot be cancelled — the valuation ledger is immutable. "
				"Post a corrective count instead."
			),
			title=_("Immutable Ledger"),
		)
