# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

"""SAP Moving Average posting kernel.

Phase-1 stub: proves the routing dispatch end-to-end. The Phase-2 kernel
replaces the body with the full posting flow:
Normalize -> Validate (period open) -> Lock (IPB prev->current) -> Compute ->
Write (SME + IVE + IPB + SLE-compatible rows + GL) -> Queue (projections).
"""

import frappe
from frappe import _


def post_via_sap_ma_kernel(controller, sl_entries):
	"""Entry point called by the fork's routing dispatch.

	:param controller: the submitting stock voucher's controller instance
	:param sl_entries: the SLE dicts core prepared for this voucher's routed items
	"""
	frappe.throw(
		_(
			"SAP Moving Average posting kernel is not yet enabled (Phase 2). "
			"Routing dispatch reached the kernel for {0} {1} with {2} entries."
		).format(controller.doctype, controller.name, len(sl_entries)),
		title=_("Kernel Not Enabled"),
	)
