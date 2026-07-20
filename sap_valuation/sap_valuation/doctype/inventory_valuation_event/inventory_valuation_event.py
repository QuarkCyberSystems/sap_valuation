# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from sap_valuation.shared.immutable import block_delete, block_update, kernel_only_insert


class InventoryValuationEvent(Document):
	def before_insert(self):
		kernel_only_insert(self)
		self.validate_source_reference()

	def validate_source_reference(self):
		# Apr 22 decision: source reference is mandatory on ALL valuation events,
		# including value-only ones (landed cost split rows need source_detail_name).
		if not (self.source_doctype and self.source_docname):
			frappe.throw(
				_("Inventory Valuation Event requires a source document reference (source_doctype + source_docname)."),
				title=_("Missing Source Reference"),
			)

	def validate(self):
		block_update(self)

	def on_trash(self):
		block_delete(self)
