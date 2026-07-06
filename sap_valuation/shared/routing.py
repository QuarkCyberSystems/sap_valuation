# Copyright (c) 2026, Quark Cyber Systems
# License: GNU General Public License v3. See license.txt

"""Valuation-method routing registry.

The erpnext fork consults this before creating SLEs: items whose
valuation_method has a registered kernel are posted through it; everything
else follows the unmodified core path. Registration happens via the
``sap_valuation_kernels`` hook so additional kernels (SAP Standard Cost,
Phase 3) plug in without further core edits.
"""

import frappe

# Enum values added to Item.valuation_method by the fork. "SAP Standard Cost"
# deliberately differs from core develop's "Standard Cost" (PR 56570), whose
# semantics are incompatible (see consolidated design DR-01).
SAP_VALUATION_METHODS = ("SAP Moving Average", "SAP Standard Cost")


def get_kernel_map():
	"""method -> dotted path of the posting kernel entrypoint."""
	hooks = frappe.get_hooks("sap_valuation_kernels") or {}
	kernel_map = {}
	for method, paths in hooks.items():
		if isinstance(paths, (list, tuple)):
			kernel_map[method] = paths[-1]
		else:
			kernel_map[method] = paths
	return kernel_map


def get_kernel(valuation_method):
	"""Return the kernel callable for a method, or None for core methods."""
	path = get_kernel_map().get(valuation_method)
	return frappe.get_attr(path) if path else None


def get_incoming_rate(args, valuation_method):
	"""Incoming-rate resolver for kernel-valued items (``sap_valuation_incoming_rate`` hook).

	MAP items are always valued at the current period moving average from
	Inventory Period Balance — never from SLE state or the generic fallback
	chain (period-MAP-for-issues rule, signed MAP plan).
	"""
	from frappe import _

	item_code = args.get("item_code")
	company = args.get("company")
	if not company and args.get("warehouse"):
		company = frappe.get_cached_value("Warehouse", args.get("warehouse"), "company")

	if valuation_method != "SAP Moving Average":
		frappe.throw(
			_("No incoming-rate resolver for valuation method {0}.").format(valuation_method)
		)

	include_warehouse = frappe.get_cached_value("Item", item_code, "valuation_includes_warehouse")
	filters = {"company": company, "item_code": item_code}
	filters["warehouse"] = (args.get("warehouse") or "") if include_warehouse else ""

	row = frappe.get_all(
		"Inventory Period Balance",
		filters=filters,
		fields=["moving_avg_price", "frozen_map", "is_negative"],
		order_by="period_year desc, period_month desc",
		limit=1,
	)
	if not row:
		return 0.0
	if row[0].is_negative:
		return row[0].frozen_map or 0.0
	return row[0].moving_avg_price or 0.0
