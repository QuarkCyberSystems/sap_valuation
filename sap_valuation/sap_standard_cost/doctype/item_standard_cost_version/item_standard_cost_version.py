# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime

from sap_valuation.sap_standard_cost.engine import StdEngine, r2


class ItemStandardCostVersion(Document):
	def validate(self):
		if not (1 <= (self.valid_from_month or 0) <= 12):
			frappe.throw(_("Valid From Month must be 1-12."))
		self.effective_from = f"{self.valid_from_year}-{self.valid_from_month:02d}-01"
		if flt(self.standard_cost) <= 0:
			frappe.throw(_("Standard Cost must be positive."))

		from erpnext.stock.utils import get_valuation_method

		if get_valuation_method(self.item_code, self.company) != "SAP Standard Cost":
			frappe.throw(
				_("{0} is not a SAP Standard Cost item.").format(self.item_code)
			)

		include_wh = frappe.get_cached_value("Item", self.item_code, "valuation_includes_warehouse")
		self.warehouse = self.warehouse if include_wh else None

		if self.status == "RELEASED" and frappe.db.exists(
			"Item Standard Cost Version",
			{
				"company": self.company, "item_code": self.item_code,
				"warehouse": ("in", (self.warehouse or "", None)),
				"valid_from_year": self.valid_from_year,
				"valid_from_month": self.valid_from_month, "status": "RELEASED",
				"name": ("!=", self.name),
			},
		):
			frappe.throw(
				_("A RELEASED version already exists for this scope and period."),
				title=_("Duplicate Version"),
			)

		if not self.is_new():
			old_status = frappe.db.get_value(self.doctype, self.name, "status")
			if old_status == "RELEASED" and not self.flags.via_release_flow:
				frappe.throw(
					_("Released cost versions are immutable. Release a new version instead."),
					title=_("Immutable"),
				)

	@frappe.whitelist()
	def release(self):
		"""Release this version: supersede the prior one and, when the change is
		effective in an already-active period, post the boundary revaluation
		triplet (Rev Beg / REV In / REV out) at the release date (DR-12)."""
		if self.status != "DRAFT":
			frappe.throw(_("Only DRAFT versions can be released."))

		prior_name = frappe.db.get_value(
			"Item Standard Cost Version",
			{
				"company": self.company, "item_code": self.item_code,
				"warehouse": ("in", (self.warehouse or "", None)), "status": "RELEASED",
				"name": ("!=", self.name),
			},
			order_by="valid_from_year desc, valid_from_month desc",
		)
		prior_sc = None
		if prior_name:
			prior_sc = flt(frappe.db.get_value("Item Standard Cost Version", prior_name, "standard_cost"))

		self.flags.via_release_flow = True
		self.status = "RELEASED"
		self.supersedes_version = prior_name
		self.released_on = now_datetime()
		self.released_by = frappe.session.user
		self.save(ignore_permissions=False)

		if prior_name:
			frappe.db.set_value("Item Standard Cost Version", prior_name, "status", "SUPERSEDED")

		if prior_sc is not None and flt(self.standard_cost) != prior_sc:
			self.post_revaluation_triplet(prior_sc)
		return self.name

	def post_revaluation_triplet(self, old_sc):
		engine = StdEngine(self.company, self.item_code, self.warehouse)
		today = getdate(frappe.utils.nowdate())
		delta = flt(self.standard_cost) - old_sc

		if engine.view == "MTD":
			beg = engine.beg_qty_mtd(today.year, today.month)
			in_qty = engine.in_qty_mtd(today.year, today.month)
			out_qty = -engine.out_qty_mtd(today.year, today.month)
		else:
			beg = engine._reval_qty_at("Rev Beg", today, sc_new=flt(self.standard_cost), sc_old=old_sc)
			in_qty = engine._reval_qty_at("REV In", today, sc_new=flt(self.standard_cost), sc_old=old_sc)
			out_qty = engine._reval_qty_at("REV out", today, sc_new=flt(self.standard_cost), sc_old=old_sc)

		source = (self.doctype, self.name)
		for trans, qty in (("Rev Beg", beg), ("REV In", in_qty)):
			amount = r2(delta * qty)
			if amount:
				engine.post(trans=trans, posting_date=today, source=source,
					sc=self.standard_cost, ac=old_sc, t_sc_override=amount,
					cost_version=self.name)
		out_amount = r2(-(delta * out_qty))
		if out_amount:
			engine.post(trans="REV out", posting_date=today, source=source,
				sc=self.standard_cost, ac=old_sc, t_sc_override=out_amount,
				cost_version=self.name)
		self.db_set("revaluation_posted", 1, update_modified=False)

	def on_trash(self):
		if self.status != "DRAFT":
			frappe.throw(_("Only DRAFT versions can be deleted."))
