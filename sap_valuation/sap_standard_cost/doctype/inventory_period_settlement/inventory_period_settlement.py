# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from sap_valuation.shared.immutable import KERNEL_FLAG


class InventoryPeriodSettlement(Document):
	def before_insert(self):
		if not frappe.flags.get(KERNEL_FLAG):
			frappe.throw(_("Settlements are created by the settlement engine only."))

	def on_trash(self):
		frappe.throw(_("Settlements are immutable. Reverse instead."), title=_("Immutable Ledger"))
