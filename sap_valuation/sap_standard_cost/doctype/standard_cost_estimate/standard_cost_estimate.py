# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

"""Standard Cost Estimate — single-level BOM roll-up feeding the cost-version
catalog. Multi-level roll-up is out of scope in this release (OI-3)."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class StandardCostEstimate(Document):
	@frappe.whitelist()
	def calculate(self):
		"""Explode the BOM one level and price each component."""
		if self.bom and not self.components:
			bom = frappe.get_doc("BOM", self.bom)
			for row in bom.items:
				self.append("components", {
					"item_code": row.item_code,
					"qty": flt(row.qty) / flt(bom.quantity or 1),
					"rate_source": "LEAF_STD",
				})
		if not self.components:
			frappe.throw(_("Add components or link a BOM first."))

		from sap_valuation.sap_standard_cost.engine import get_active_standard_cost

		total = 0.0
		target_date = f"{self.valid_from_year}-{self.valid_from_month:02d}-01"
		for row in self.components:
			if row.rate_source == "LEAF_STD":
				from erpnext.stock.utils import get_valuation_method

				if get_valuation_method(row.item_code, self.company) == "SAP Standard Cost":
					scv = get_active_standard_cost(self.company, row.item_code, None, target_date)
					row.rate = flt(scv.standard_cost)
				else:
					row.rate = flt(frappe.get_cached_value("Item", row.item_code, "valuation_rate"))
			elif row.rate_source == "VALUATION_RATE":
				row.rate = flt(frappe.get_cached_value("Item", row.item_code, "valuation_rate"))
			if not flt(row.rate):
				frappe.throw(_("Row {0}: no rate resolvable for {1}.").format(row.idx, row.item_code))
			row.amount = flt(flt(row.qty) * flt(row.rate), 2)
			total += row.amount

		self.material_cost = flt(total, 2)
		self.overhead_amount = flt(total * flt(self.overhead_percent) / 100, 2)
		self.standard_cost = flt(self.material_cost + self.overhead_amount, 6)
		self.status = "CALCULATED"
		self.save(ignore_permissions=True)
		return self.standard_cost

	@frappe.whitelist()
	def release(self):
		"""Create and release the resulting Item Standard Cost Version."""
		if self.status != "CALCULATED":
			frappe.throw(_("Calculate the estimate first."))
		scv = frappe.get_doc({
			"doctype": "Item Standard Cost Version", "company": self.company,
			"item_code": self.item_code, "valid_from_year": self.valid_from_year,
			"valid_from_month": self.valid_from_month, "standard_cost": self.standard_cost,
			"source_type": "SCE", "remarks": _("Released from {0}").format(self.name),
		})
		scv.insert(ignore_permissions=True)
		scv.release()
		self.db_set({"status": "RELEASED", "cost_version": scv.name})
		return scv.name
