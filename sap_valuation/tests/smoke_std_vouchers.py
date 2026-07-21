"""STD voucher integration — bench --site <site> execute sap_valuation.tests.smoke_std_vouchers.run

Drives REAL vouchers through the STD routing: PR -> Rec (SC + PPV legs),
DN -> Iss at SC, Stock Count -> SC-, PI diff -> PPV, then a Settlement Run.
Rolled back unless commit=True.
"""

import frappe
from frappe.utils import flt, get_first_day, getdate, nowdate

from sap_valuation.tests.smoke_edges import make_dn, make_pr
from sap_valuation.tests.smoke_kernel import ensure_masters, get_company
from sap_valuation.tests.smoke_std import ensure_std_masters

CHECKS = []
ITEM = "_STDV-ITEM"


def check(label, ok, detail=""):
	CHECKS.append((label, bool(ok)))
	print(("PASS " if ok else "FAIL ") + label + (f" — {detail}" if detail and not ok else ""))


def run(commit=False):
	wh = ensure_masters()
	company = get_company()
	ensure_std_masters(company)
	frappe.db.set_single_value("Buying Settings", "maintain_same_rate", 0)
	frappe.db.set_single_value("Accounts Settings", "over_billing_allowance", 50)

	if not frappe.db.exists("Item", ITEM):
		frappe.get_doc({"doctype": "Item", "item_code": ITEM, "item_name": ITEM,
			"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, limit=1, pluck="name")[0],
			"stock_uom": frappe.get_all("UOM", limit=1, pluck="name")[0],
			"is_stock_item": 1, "valuation_method": "SAP Standard Cost",
			"settlement_view": "MTD"}).insert(ignore_permissions=True)

	today = getdate(nowdate())
	scv = frappe.get_doc({
		"doctype": "Item Standard Cost Version", "company": company, "item_code": ITEM,
		"valid_from_year": today.year, "valid_from_month": today.month, "standard_cost": 10,
		"source_type": "MANUAL_OVERRIDE",
	})
	scv.insert(ignore_permissions=True)
	scv.release()

	# ---- PR 100 @ AC 12 -> Rec at SC 10, PPV 200
	pr = make_pr(ITEM, wh, 100, 12)
	ive = frappe.get_all("Inventory Valuation Event",
		filters={"source_docname": pr.name}, fields=["std_trans", "total_sc", "total_ac"])
	check("PR routes as Rec (SC 1000 / AC 1200)",
		ive and ive[0].std_trans == "Rec" and flt(ive[0].total_sc) == 1000
		and flt(ive[0].total_ac) == 1200, str(ive))
	gl = frappe.get_all("GL Entry", filters={"voucher_no": pr.name, "is_cancelled": 0},
		fields=["account", "debit", "credit", "valuation_event_id"])
	dr = flt(sum(g.debit for g in gl), 2)
	check("PR GL balanced with PPV leg (dr 1200, all tagged)",
		dr == flt(sum(g.credit for g in gl), 2) == 1200
		and all(g.valuation_event_id for g in gl), f"dr {dr}")
	sle = frappe.get_all("Stock Ledger Entry", filters={"voucher_no": pr.name},
		fields=["posted_via_sap_kernel", "valuation_rate", "stock_value_difference"])
	check("PR SLE at standard (rate 10, svd 1000)",
		sle and sle[0].posted_via_sap_kernel and flt(sle[0].valuation_rate) == 10
		and flt(sle[0].stock_value_difference) == 1000, str(sle))

	# ---- DN 30 -> Iss at SC (no variance)
	dn = make_dn(ITEM, wh, 30)
	ive = frappe.get_all("Inventory Valuation Event",
		filters={"source_docname": dn.name}, fields=["std_trans", "total_sc", "total_ac"])
	check("DN routes as Iss at SC (-300, no variance)",
		ive and ive[0].std_trans == "Iss" and flt(ive[0].total_sc) == -300
		and flt(ive[0].total_ac) == 0, str(ive))

	# ---- negative stock blocked
	try:
		make_dn(ITEM, wh, 500)
		check("STD negative stock blocked", False, "submitted")
	except frappe.ValidationError:
		check("STD negative stock blocked", True)

	# ---- Stock Count shortage -> SC- at standard
	sc_doc = frappe.get_doc({
		"doctype": "Stock Count", "company": company, "posting_date": nowdate(),
		"items": [{"item_code": ITEM, "warehouse": wh, "counted_qty": 65}],
	})
	sc_doc.insert(ignore_permissions=True)
	sc_doc.submit()
	ive = frappe.get_all("Inventory Valuation Event",
		filters={"source_docname": sc_doc.name}, fields=["std_trans", "total_sc"])
	check("Count shortage routes as SC- (-50)",
		ive and ive[0].std_trans == "SC-" and flt(ive[0].total_sc) == -50, str(ive))

	# ---- PI price difference -> PPV pool (LC-shaped)
	pi = frappe.get_doc({
		"doctype": "Purchase Invoice", "company": company, "supplier": "_SMK Supplier",
		"posting_date": nowdate(),
		"items": [{"item_code": ITEM, "qty": 100, "rate": 13, "warehouse": wh,
			"purchase_receipt": pr.name, "pr_detail": pr.items[0].name}],
	})
	pi.insert(ignore_permissions=True)
	pi.submit()
	ive = frappe.get_all("Inventory Valuation Event",
		filters={"source_docname": pi.name, "std_trans": "LC"}, fields=["total_ac"])
	check("PI diff 100 lands in PPV pool", ive and flt(ive[0].total_ac) == 100, str(ive))

	# ---- MR21 blocked for STD; transfers blocked
	try:
		rv = frappe.get_doc({"doctype": "Stock Revaluation", "company": company,
			"posting_date": nowdate(),
			"items": [{"item_code": ITEM, "warehouse": wh, "new_valuation_rate": 15}]})
		rv.insert(ignore_permissions=True)
		check("MR21 blocked for STD", False, "inserted")
	except frappe.ValidationError:
		check("MR21 blocked for STD", True)

	# ---- Settlement Run: pool 200 (PPV) + 100 (PI diff) = 300; end 65 of 100
	run_doc = frappe.get_doc({
		"doctype": "Inventory Period Settlement Run", "company": company,
		"period_year": today.year, "period_month": today.month,
		"run_type": "INITIAL_CLOSE",
	})
	run_doc.insert(ignore_permissions=True)
	run_doc.submit()
	run_doc.reload()
	sett = frappe.get_all("Inventory Period Settlement",
		filters={"item_code": ITEM, "cancelled": 0}, fields=["*"])
	expected_es = flt(300 * 65 / 100, 2)
	expected_out = flt(300 * 35 / 100, 2)
	check("Settlement Run settles the scope",
		run_doc.status == "Completed" and run_doc.scopes_settled >= 1, run_doc.status)
	check(f"Settlement 300-pool split {expected_es}/{expected_out}",
		sett and flt(sett[0].es_var, 2) == expected_es and flt(sett[0].out_var, 2) == expected_out,
		f"{sett and sett[0].es_var}/{sett and sett[0].out_var}")

	# ---- posting into the settled period now blocked
	try:
		make_pr(ITEM, wh, 5, 12, posting_date=str(get_first_day(nowdate())))
		check("settled period blocks vouchers", False, "submitted")
	except frappe.ValidationError:
		check("settled period blocks vouchers", True)

	failed = [x for x in CHECKS if not x[1]]
	print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
	if commit and not failed:
		frappe.db.commit()
	else:
		frappe.db.rollback()
	if failed:
		raise Exception("STD voucher failures: " + "; ".join(x[0] for x in failed))
