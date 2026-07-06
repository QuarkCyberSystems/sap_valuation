# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

"""Universal cancellation rule for SAP-valuation items (May 6 decision).

Direct cancellation (docstatus 1 -> 2) is NEVER allowed for a document that
contains routed items — even same-period with no downstream consumption,
because an intervening revaluation could have landed. The user is redirected
to Create Cancellation, which posts a dated reversal document of the same
doctype and preserves the immutable ledger.
"""

import frappe
from frappe import _


def get_sap_methods():
	from sap_valuation.shared.routing import SAP_VALUATION_METHODS

	return SAP_VALUATION_METHODS


def has_routed_items(doc):
	from erpnext.stock.utils import get_valuation_method

	sap_methods = get_sap_methods()
	for row in doc.get("items") or []:
		item_code = row.get("item_code")
		if not item_code:
			continue
		if get_valuation_method(item_code, doc.get("company")) in sap_methods:
			return True
	return False


def block_direct_cancel(doc, method=None):
	if not has_routed_items(doc):
		return
	frappe.throw(
		_(
			"This document contains SAP-valuation items. Direct cancellation would mutate the "
			"immutable ledger. Use <b>Create Cancellation</b> to post a dated reversal instead."
		),
		title=_("Cancellation Blocked"),
	)
