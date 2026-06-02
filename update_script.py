import re

with open('/home/bsoft/frappe16-bench/apps/slcm/slcm/pace/web_form/pace_application_form/pace_application_form.js', 'r') as f:
    content = f.read()

# Fix 1: submit flow
old_submit_flow = """	var prog = wf.get_value('programme');
	_paceShowLoading(__('Calculating Fee...'));

	frappe.call({
		method: 'slcm.pace.web_form.pace_application_form.pace_application_form.get_pace_admission_fee',
		args: {
			application: {
				programme: prog,
				academic_year: wf.get_value('academic_year'),
				nationality: wf.get_value('nationality')
			}
		},
		callback: function (r) {
			_paceHideLoading();
			if (r && r.exc) {
				paceShowToast(_paceErrFromCall(r), 'error', 8000);
				return;
			}
			var fee = (r.message && r.message.fee) || 0;

			_paceShowConfirmModal(fee, 'INR', prog, function () {
				_paceShowLoading(__('Processing Application...'));

				paceHandleSaveDraft({ ignore_mandatory: false, silent: true }).then(function (msg) {
					var docname = (msg && msg.name) || (wf && wf.doc && wf.doc.name) || _paceGetDocName();
					if (!docname) {
						_paceHideLoading();
						paceShowToast(__('Could not save application. Save draft once, then try payment again.'), 'error', 8000);
						return;
					}
					try {
						if (wf && wf.doc) wf.doc.name = docname;
					} catch (eSync) { /* keep going */ }
					// Defer payment init to the next tick so web form / URL state match the saved name (fixes first-click Razorpay).
					setTimeout(function () {
						frappe.call({
							method: 'slcm.pace.web_form.pace_application_form.pace_application_form.initiate_pace_razorpay_order',"""

new_submit_flow = """	var prog = wf.get_value('programme');
	_paceShowLoading(__('Processing Application...'));

	paceHandleSaveDraft({ ignore_mandatory: false, silent: true }).then(function (msg) {
		var docname = (msg && msg.name) || (wf && wf.doc && wf.doc.name) || _paceGetDocName();
		if (!docname) {
			_paceHideLoading();
			paceShowToast(__('Could not save application. Save draft once, then try again.'), 'error', 8000);
			return;
		}
		try {
			if (wf && wf.doc) wf.doc.name = docname;
		} catch (eSync) { /* keep going */ }

		// Now fetch the fee
		_paceShowLoading(__('Calculating Fee...'));
		frappe.call({
			method: 'slcm.pace.web_form.pace_application_form.pace_application_form.get_pace_admission_fee',
			args: {
				application: {
					programme: prog,
					academic_year: wf.get_value('academic_year'),
					nationality: wf.get_value('nationality')
				}
			},
			callback: function (r) {
				_paceHideLoading();
				if (r && r.exc) {
					paceShowToast(_paceErrFromCall(r), 'error', 8000);
					return;
				}
				var fee = (r.message && r.message.fee) || 0;

				_paceShowConfirmModal(fee, 'INR', prog, function () {
					_paceShowLoading(__('Gateway Opening...'));

					// Defer payment init to the next tick
					setTimeout(function () {
						frappe.call({
							method: 'slcm.pace.web_form.pace_application_form.pace_application_form.initiate_pace_razorpay_order',"""

content = content.replace(old_submit_flow, new_submit_flow)

# Fix 1b: remove old Gateway Opening... line that was below
old_gw = """								if (res && res.status === 'error') {
									_paceHideLoading();
									paceShowToast(String(res.message || __('Payment could not be started.')), 'error', 8000);
									return;
								}
								_paceShowLoading(__('Gateway Opening...'));
								if (!res || !res.order_id || !res.key_id) {"""
new_gw = """								if (res && res.status === 'error') {
									_paceHideLoading();
									paceShowToast(String(res.message || __('Payment could not be started.')), 'error', 8000);
									return;
								}
								if (!res || !res.order_id || !res.key_id) {"""
content = content.replace(old_gw, new_gw)

# Fix 1c: close braces for submit flow correctly since I wrapped the whole thing in a promise
old_braces = """								});
							}
						});
					}, 200);
				});
			});
		}
	});"""
new_braces = """								});
							}
						});
					}, 200);
				});
			}
		});
	});"""
content = content.replace(old_braces, new_braces)

# Fix 2: Address cascading
old_addr = """		wf.on(countryFld, function () {
			if (wf._is_syncing_address) return;
			wf.set_value(stateFld, '');
			wf.set_value(districtFld, '');
			if (cityDataFld) wf.set_value(cityDataFld, '');
		});

		wf.on(stateFld, function () {
			if (wf._is_syncing_address) return;
			wf.set_value(districtFld, '');
			if (cityDataFld) wf.set_value(cityDataFld, '');
		});"""

new_addr = """		var lastCountry = wf.get_value(countryFld);
		var lastState = wf.get_value(stateFld);

		wf.on(countryFld, function () {
			if (wf._is_syncing_address) return;
			var currentCountry = wf.get_value(countryFld);
			if (lastCountry === currentCountry) return;
			lastCountry = currentCountry;

			wf.set_value(stateFld, '');
			wf.set_value(districtFld, '');
			if (cityDataFld) wf.set_value(cityDataFld, '');
		});

		wf.on(stateFld, function () {
			if (wf._is_syncing_address) return;
			var currentState = wf.get_value(stateFld);
			if (lastState === currentState) return;
			lastState = currentState;

			wf.set_value(districtFld, '');
			if (cityDataFld) wf.set_value(cityDataFld, '');
		});"""

content = content.replace(old_addr, new_addr)

# Fix 3: Syncing address flag
old_sync = """						callback: function (r) {
							if (r && r.message) {
								if (r.message.state) wf.set_value(state_field, r.message.state);
								if (r.message.country) wf.set_value(country_field, r.message.country);
							}
						}"""

new_sync = """						callback: function (r) {
							if (r && r.message) {
								wf._is_syncing_address = true;
								if (r.message.state) wf.set_value(state_field, r.message.state);
								if (r.message.country) wf.set_value(country_field, r.message.country);
								setTimeout(function() { wf._is_syncing_address = false; }, 200);
							}
						}"""

content = content.replace(old_sync, new_sync)

with open('/home/bsoft/frappe16-bench/apps/slcm/slcm/pace/web_form/pace_application_form/pace_application_form.js', 'w') as f:
    f.write(content)

print("Done")
