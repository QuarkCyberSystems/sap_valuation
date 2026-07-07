"""Edge-scenario smoke — bench --site badiav16.localhost execute sap_valuation.tests.smoke_edges.run

Covers the scenarios previously proven only in the reference simulator:
backdated C1/C2 (negative prior period, client-locked anchors), PI invoice
difference via stock ratio, purchase return with reference, company-scope
transfer neutrality, warehouse-scope two-leg transfer, full issue-out reset,
and SI update_stock issues. Rolled back unless commit=True.
"""

import frappe
from frappe.utils import add_months, flt, get_first_day, nowdate

from sap_valuation.tests.smoke_kernel import COMPANY, ensure_masters

CHECKS = []


def check(label, ok, detail=""):
	CHECKS.append((label, bool(ok)))
	print(("PASS " if ok else "FAIL ") + label + (f" — {detail}" if detail and not ok else ""))


def make_item(code, include_warehouse=0):
	if not frappe.db.exists("Item", code):
		frappe.get_doc({
			"doctype": "Item", "item_code": code, "item_name": code,
			"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, limit=1, pluck="name")[0],
			"stock_uom": "Nos" if frappe.db.exists("UOM", "Nos") else frappe.get_all("UOM", limit=1, pluck="name")[0],
			"is_stock_item": 1, "valuation_method": "SAP Moving Average",
			"valuation_includes_warehouse": include_warehouse,
		}).insert(ignore_permissions=True)
	return code


def make_pr(item, wh, qty, rate, posting_date=None):
	pr = frappe.get_doc({
		"doctype": "Purchase Receipt", "company": COMPANY, "supplier": "_SMK Supplier",
		"posting_date": posting_date or nowdate(), "set_posting_time": 1,
		"items": [{"item_code": item, "qty": qty, "rate": rate, "warehouse": wh}],
	})
	pr.insert(ignore_permissions=True)
	pr.submit()
	return pr


def make_dn(item, wh, qty, posting_date=None):
	dn = frappe.get_doc({
		"doctype": "Delivery Note", "company": COMPANY, "customer": "_SMK Customer",
		"posting_date": posting_date or nowdate(), "set_posting_time": 1,
		"items": [{"item_code": item, "qty": qty, "rate": 25, "warehouse": wh}],
	})
	dn.insert(ignore_permissions=True)
	dn.submit()
	return dn


def ipb(item, warehouse=""):
	rows = frappe.get_all(
		"Inventory Period Balance",
		filters={"company": COMPANY, "item_code": item, "warehouse": warehouse},
		fields=["*"], order_by="period_year desc, period_month desc", limit=1,
	)
	return rows[0] if rows else None


def ipb_period(item, year, month, warehouse=""):
	rows = frappe.get_all(
		"Inventory Period Balance",
		filters={"company": COMPANY, "item_code": item, "warehouse": warehouse,
			"period_year": year, "period_month": month},
		fields=["*"], limit=1,
	)
	return rows[0] if rows else None


def run(commit=False):
	wh = ensure_masters()
	# invoice differences require PI rates to diverge from the PR
	frappe.db.set_single_value("Buying Settings", "maintain_same_rate", 0)
	frappe.db.set_single_value("Accounts Settings", "over_billing_allowance", 50)
	prior = get_first_day(add_months(nowdate(), -1))
	if not frappe.db.exists("Inventory Period", {"company": COMPANY, "period_name": prior.strftime("%Y-%m")}):
		frappe.get_doc({
			"doctype": "Inventory Period", "company": COMPANY,
			"start_date": prior, "status": "PREV_OPEN_UNSETTLED",
		}).insert(ignore_permissions=True)

	# ============ C1: prior negative, current positive (anchors 252/587/30.8947)
	it = make_item("_SMK-C1")
	make_pr(it, wh, 10, 15, posting_date=str(prior))   # prior: 10/150
	make_dn(it, wh, 20, posting_date=str(prior))        # prior: -10/-150 frozen 15
	p = ipb_period(it, prior.year, prior.month)
	check("C1 prior -10/-150 frozen 15",
		flt(p.closing_qty) == -10 and flt(p.closing_value, 2) == -150 and flt(p.frozen_map) == 15,
		f"{p.closing_qty}/{p.closing_value}/{p.frozen_map}")

	make_pr(it, wh, 20, 17.5)                            # current: crosses to +10/175, MAP 17.5
	rv = frappe.get_doc({
		"doctype": "Stock Revaluation", "company": COMPANY, "posting_date": nowdate(),
		"items": [{"item_code": it, "warehouse": wh, "new_valuation_rate": 20}],
	})
	rv.insert(ignore_permissions=True)
	rv.submit()                                          # current: 10/200, MAP 20 (client setup)
	c = ipb(it)
	check("C1 current 10/200 MAP 20",
		flt(c.closing_qty) == 10 and flt(c.closing_value, 2) == 200, f"{c.closing_qty}/{c.closing_value}")

	make_pr(it, wh, 9, 43, posting_date=str(prior))      # THE backdated receipt
	p = ipb_period(it, prior.year, prior.month)
	c = ipb(it)
	check("C1 prior after: -1/-15, PRD 252",
		flt(p.closing_qty) == -1 and flt(p.closing_value, 2) == -15 and flt(p.prd_value, 2) == -252,
		f"{p.closing_qty}/{p.closing_value}/{p.prd_value}")
	check("C1 current after: 19/587, MAP 30.8947",
		flt(c.closing_qty) == 19 and flt(c.closing_value, 2) == 587
		and flt(c.moving_avg_price, 4) == 30.8947,
		f"{c.closing_qty}/{c.closing_value}/{c.moving_avg_price}")
	check("C1 absorb 252 in adjust bucket", flt(c.adjust_value, 2) == 252, str(c.adjust_value))

	# ============ C2: both periods negative (anchors 247/140/56, final 6@43)
	it = make_item("_SMK-C2")
	make_pr(it, wh, 5, 15, posting_date=str(prior))      # prior 5/75
	make_dn(it, wh, 10, posting_date=str(prior))          # prior -5/-75 frozen 15
	make_pr(it, wh, 2, 15)                                # current: opening -5 -> -3/-45 (PRD 0)
	c = ipb(it)
	check("C2 current -3/-45 frozen 15",
		flt(c.closing_qty) == -3 and flt(c.closing_value, 2) == -45 and flt(c.frozen_map) == 15,
		f"{c.closing_qty}/{c.closing_value}/{c.frozen_map}")

	make_pr(it, wh, 9, 43, posting_date=str(prior))      # backdated into negative prior
	p = ipb_period(it, prior.year, prior.month)
	c = ipb(it)
	check("C2 prior: closing 4/172, PRD 140",
		flt(p.closing_qty) == 4 and flt(p.closing_value, 2) == 172 and flt(p.prd_value, 2) == -140,
		f"{p.closing_qty}/{p.closing_value}/{p.prd_value}")
	check("C2 current: 6/258 MAP 43, absorb 56",
		flt(c.closing_qty) == 6 and flt(c.closing_value, 2) == 258
		and flt(c.moving_avg_price, 2) == 43 and flt(c.adjust_value, 2) == 56,
		f"{c.closing_qty}/{c.closing_value}/{c.moving_avg_price}/{c.adjust_value}")

	# ============ PI invoice difference via stock ratio
	it = make_item("_SMK-PIDIFF")
	pr = make_pr(it, wh, 100, 10)
	make_dn(it, wh, 20)                                   # ratio 80/100 = 0.8
	pi = frappe.get_doc({
		"doctype": "Purchase Invoice", "company": COMPANY, "supplier": "_SMK Supplier",
		"posting_date": nowdate(),
		"items": [{
			"item_code": it, "qty": 100, "rate": 11, "warehouse": wh,
			"purchase_receipt": pr.name, "pr_detail": pr.items[0].name,
		}],
	})
	pi.insert(ignore_permissions=True)
	pi.submit()
	ive = frappe.get_all("Inventory Valuation Event",
		filters={"source_docname": pi.name, "reason_code": "invoice_diff"},
		fields=["value_delta", "expense_portion"])
	check("PI diff 100: 80 inv / 20 exp (ratio 0.8)",
		ive and flt(ive[0].value_delta, 2) == 80.00 and flt(ive[0].expense_portion, 2) == 20.00,
		str(ive))
	c = ipb(it)
	check("PI diff MAP recalc", flt(c.moving_avg_price, 2) == flt((800 + 80) / 80, 2),
		str(c.moving_avg_price))

	# ============ purchase return WITH reference at original cost
	it = make_item("_SMK-RET")
	pr = make_pr(it, wh, 100, 10)
	make_pr(it, wh, 50, 20)                               # MAP 13.3333
	ret = frappe.get_doc({
		"doctype": "Purchase Receipt", "company": COMPANY, "supplier": "_SMK Supplier",
		"posting_date": nowdate(), "is_return": 1, "return_against": pr.name,
		"items": [{
			"item_code": it, "qty": -30, "rate": 10, "warehouse": wh,
			"purchase_receipt_item": pr.items[0].name,
		}],
	})
	ret.insert(ignore_permissions=True)
	ret.submit()
	ive = frappe.get_all("Inventory Valuation Event",
		filters={"source_docname": ret.name}, fields=["reason_code", "value_delta"])
	c = ipb(it)
	check("purchase return w/ref at original 10 (300)",
		ive and ive[0].reason_code == "return_with_ref" and flt(ive[0].value_delta, 2) == -300.00,
		str(ive))
	check("return MAP recalc (1700/120)", flt(c.moving_avg_price, 4) == flt(1700 / 120, 4),
		str(c.moving_avg_price))

	# ============ company-scope transfer: value-neutral
	it = make_item("_SMK-TRF")
	abbr = frappe.db.get_value("Company", COMPANY, "abbr")
	wh2 = f"_SMK Stores 2 - {abbr}"
	if not frappe.db.exists("Warehouse", wh2):
		frappe.get_doc({"doctype": "Warehouse", "warehouse_name": "_SMK Stores 2",
			"company": COMPANY}).insert(ignore_permissions=True)
	make_pr(it, wh, 40, 10)
	before = ipb(it)
	se = frappe.get_doc({
		"doctype": "Stock Entry", "company": COMPANY, "stock_entry_type": "Material Transfer",
		"posting_date": nowdate(),
		"items": [{"item_code": it, "qty": 15, "s_warehouse": wh, "t_warehouse": wh2}],
	})
	se.insert(ignore_permissions=True)
	se.submit()
	after = ipb(it)
	check("company-scope transfer is value-neutral",
		flt(after.closing_qty) == flt(before.closing_qty)
		and flt(after.closing_value, 2) == flt(before.closing_value, 2)
		and flt(after.moving_avg_price, 6) == flt(before.moving_avg_price, 6),
		f"{after.closing_qty}/{after.closing_value}")
	check("transfer posts no GL",
		not frappe.db.exists("GL Entry", {"voucher_no": se.name, "is_cancelled": 0}))
	smes = frappe.get_all("Stock Movement Event", filters={"source_docname": se.name},
		pluck="movement_type")
	check("transfer SMEs both legs", sorted(smes) == ["transfer_in", "transfer_out"], str(smes))
	bin_qty = flt(frappe.db.get_value("Bin", {"item_code": it, "warehouse": wh2}, "actual_qty"))
	check("bin at destination", bin_qty == 15, str(bin_qty))

	# ============ warehouse-scope transfer: two-leg at source MAP
	it = make_item("_SMK-TRFW", include_warehouse=1)
	make_pr(it, wh, 40, 12)
	se = frappe.get_doc({
		"doctype": "Stock Entry", "company": COMPANY, "stock_entry_type": "Material Transfer",
		"posting_date": nowdate(),
		"items": [{"item_code": it, "qty": 10, "s_warehouse": wh, "t_warehouse": wh2}],
	})
	se.insert(ignore_permissions=True)
	se.submit()
	src = ipb(it, warehouse=wh)
	dst = ipb(it, warehouse=wh2)
	check("wh-scope source 30/360", flt(src.closing_qty) == 30 and flt(src.closing_value, 2) == 360,
		f"{src.closing_qty}/{src.closing_value}")
	check("wh-scope dest 10/120 MAP 12", flt(dst.closing_qty) == 10 and flt(dst.closing_value, 2) == 120,
		f"{dst.closing_qty}/{dst.closing_value}")

	# ============ full issue-out: counter + MAP reset
	it = make_item("_SMK-ZERO")
	make_pr(it, wh, 25, 10)
	make_dn(it, wh, 25)
	c = ipb(it)
	check("issue-out resets: qty 0 value 0 counter 0 MAP 0",
		flt(c.closing_qty) == 0 and flt(c.closing_value, 2) == 0
		and flt(c.total_received_since_zero) == 0 and flt(c.moving_avg_price) == 0,
		f"{c.closing_qty}/{c.closing_value}/{c.total_received_since_zero}/{c.moving_avg_price}")

	# ============ SI update_stock issue
	it = make_item("_SMK-SI")
	make_pr(it, wh, 10, 10)
	si = frappe.get_doc({
		"doctype": "Sales Invoice", "company": COMPANY, "customer": "_SMK Customer",
		"posting_date": nowdate(), "update_stock": 1,
		"items": [{"item_code": it, "qty": 4, "rate": 30, "warehouse": wh}],
	})
	si.insert(ignore_permissions=True)
	si.submit()
	c = ipb(it)
	check("SI update_stock issue at MAP", flt(c.closing_qty) == 6 and flt(c.closing_value, 2) == 60,
		f"{c.closing_qty}/{c.closing_value}")

	failed = [x for x in CHECKS if not x[1]]
	print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
	if commit and not failed:
		frappe.db.commit()
	else:
		frappe.db.rollback()
	if failed:
		raise Exception("edge smoke failures: " + "; ".join(x[0] for x in failed))
