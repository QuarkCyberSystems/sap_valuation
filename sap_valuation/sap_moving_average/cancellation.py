# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

"""Create Cancellation — the only legal way to undo a posted document that
contains SAP-valuation items (signed MAP plan; May 6 universal rule).

Creates a new draft of the SAME doctype with is_cancellation = 1 and
cancellation_against set, items copied from the original, posting_date
defaulted to today. On submit the kernel posts dated mirror events; both
documents survive at docstatus 1.
"""

import frappe
from frappe import _
from frappe.utils import nowdate

CANCELLABLE = (
	"Purchase Receipt",
	"Delivery Note",
	"Stock Entry",
	"Purchase Invoice",
	"Sales Invoice",
	"Subcontracting Receipt",
	"Landed Cost Voucher",
)


@frappe.whitelist()
def make_cancellation(doctype, name):
	if doctype not in CANCELLABLE:
		frappe.throw(_("{0} does not support Cancellation documents.").format(_(doctype)))

	original = frappe.get_doc(doctype, name)
	original.check_permission("cancel")

	if original.docstatus != 1:
		frappe.throw(_("Only submitted documents can be cancelled."))
	if original.get("is_cancellation"):
		frappe.throw(_("{0} is itself a Cancellation document.").format(name))
	if frappe.db.exists(
		doctype, {"cancellation_against": name, "is_cancellation": 1, "docstatus": ("<", 2)}
	):
		frappe.throw(
			_("A Cancellation document already exists for {0}.").format(name),
			title=_("Double Reversal Blocked"),
		)

	cancellation = frappe.copy_doc(original)
	cancellation.is_cancellation = 1
	cancellation.cancellation_against = name
	cancellation.posting_date = nowdate()
	if cancellation.meta.has_field("set_posting_time"):
		cancellation.set_posting_time = 1
	cancellation.flags.ignore_permissions = False
	cancellation.insert()
	return cancellation.name
