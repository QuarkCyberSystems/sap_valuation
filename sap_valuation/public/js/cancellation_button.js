// Copyright (c) 2026, Quark Cyber Systems
// Create Cancellation button for documents containing SAP-valuation items.
// Direct cancel is blocked server-side; this is the sanctioned path.

(() => {
	const DOCTYPES = [
		"Purchase Receipt", "Delivery Note", "Stock Entry", "Purchase Invoice",
		"Sales Invoice", "Subcontracting Receipt", "Landed Cost Voucher",
	];

	for (const doctype of DOCTYPES) {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				if (frm.doc.docstatus !== 1 || frm.doc.is_cancellation) return;

				frm.add_custom_button(__("Create Cancellation"), () => {
					frappe.confirm(
						__("Post a dated reversal document for {0}? The original stays submitted; GL mirrors on today's date.", [frm.doc.name]),
						() => {
							frappe.call({
								method: "sap_valuation.sap_moving_average.cancellation.make_cancellation",
								args: { doctype: frm.doc.doctype, name: frm.doc.name },
								freeze: true,
								callback(r) {
									if (r.message) frappe.set_route("Form", frm.doc.doctype, r.message);
								},
							});
						}
					);
				}, __("SAP Valuation"));
			},
		});
	}
})();
