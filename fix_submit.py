import re

filepath = '/home/bsoft/frappe16-bench/apps/slcm/slcm/pace/web_form/pace_application_form/pace_application_form.js'

with open(filepath, 'r') as f:
    content = f.read()

# Fix 1: _paceShowSubmissionDialog from line 1425 to 1573
old_block = """	var prog = wf.get_value('programme');
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
							method: 'slcm.pace.web_form.pace_application_form.pace_application_form.initiate_pace_razorpay_order',
							args: { application_name: docname },
							callback: function (r2) {
								if (r2 && r2.exc) {
									_paceHideLoading();
									paceShowToast(_paceErrFromCall(r2), 'error', 8000);
									return;
								}
								var res = r2.message;
								if (res && (res.status === 'free' || res.status === 'already_paid')) {
									_paceHideLoading();
									paceShowToast(res.message || __('Application submitted.'), 'success');
									setTimeout(function () { window.location.reload(); }, 1500);
									return;
								}
								if (res && res.status === 'error') {
									_paceHideLoading();
									paceShowToast(String(res.message || __('Payment could not be started.')), 'error', 8000);
									return;
								}
								_paceShowLoading(__('Gateway Opening...'));
								if (!res || !res.order_id || !res.key_id) {
									_paceHideLoading();
									paceShowToast(
										__('Payment session could not be created (missing order or gateway key). Contact support.'),
										'error',
										8000
									);
									return;
								}
								_paceLoadRazorpay(function () {
									_paceHideLoading();
									if (typeof Razorpay === 'undefined') {
										paceShowToast(__('Payment checkout failed to load. Refresh the page and try again.'), 'error');
										return;
									}
									var options = {
										key: res.key_id,
										amount: res.amount,
										currency: res.currency || 'INR',
										order_id: res.order_id,
										name: 'PACE Application Fee',
										description: 'Application Registration Fee',
										prefill: {
											name: (wf.get_value('first_name') || '') + ' ' + (wf.get_value('last_name') || ''),
											email: wf.get_value('email_address') || '',
											contact: wf.get_value('mobile_number') || ''
										},
										theme: { color: '#7B1D1D' },
										handler: function (resp) {
											_paceShowLoading(__('Verifying Payment…'));
											frappe.call({
												method: 'slcm.pace.web_form.pace_application_form.pace_application_form.verify_pace_payment_signature',
												args: {
													razorpay_payment_id: resp.razorpay_payment_id,
													razorpay_order_id: resp.razorpay_order_id,
													razorpay_signature: resp.razorpay_signature,
													assignment_name: res.assignment
												},
												callback: function (vr) {
													_paceHideLoading();
													if (vr.message && vr.message.status === 'success') {
														paceRenderSuccessPage();
													} else {
														var err = (vr.message && vr.message.message) || __('Verification failed.');
														paceShowToast(String(err), 'error', 8000);
													}
												},
												error: function () {
													_paceHideLoading();
													paceShowToast(__('Verification request failed. Please reload or contact support.'), 'error', 8000);
												}
											});
										}
									};
									try {
										var rzp = new Razorpay(options);
										rzp.on('payment.failed', function (failResp) {
											var d = failResp && failResp.error && failResp.error.description;
											paceShowToast(d ? String(d) : __('Payment failed.'), 'error', 8000);
										});
										rzp.open();
									} catch (rzpErr) {
										var rzpMsg = (rzpErr && rzpErr.message) ? String(rzpErr.message) : String(rzpErr);
										paceShowToast(__('Could not open payment window.') + ' ' + rzpMsg, 'error', 8000);
									}
								});
							},
							error: function (xhr) {
								_paceHideLoading();
								var extra = xhr && xhr.responseJSON && xhr.responseJSON._server_messages
									? _paceErrFromCall(xhr.responseJSON)
									: '';
								paceShowToast(extra || __('Could not contact the server to start payment.'), 'error', 8000);
							}
						});
					}, 0);
				}).catch(function (err) {
					_paceHideLoading();
					paceShowToast(
						(err && err.message) ? String(err.message) : __('Could not save application. Check required fields.'),
						'error',
						8000
					);
				});
			});
		},
		error: function () {
			_paceHideLoading();
			paceShowToast(__('Could not load fee. Check your connection and try again.'), 'error');
		}
	});"""

new_block = """	var prog = wf.get_value('programme');
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
					setTimeout(function () {
						frappe.call({
							method: 'slcm.pace.web_form.pace_application_form.pace_application_form.initiate_pace_razorpay_order',
							args: { application_name: docname },
							callback: function (r2) {
								if (r2 && r2.exc) {
									_paceHideLoading();
									paceShowToast(_paceErrFromCall(r2), 'error', 8000);
									return;
								}
								var res = r2.message;
								if (res && (res.status === 'free' || res.status === 'already_paid')) {
									_paceHideLoading();
									paceShowToast(res.message || __('Application submitted.'), 'success');
									setTimeout(function () { window.location.reload(); }, 1500);
									return;
								}
								if (res && res.status === 'error') {
									_paceHideLoading();
									paceShowToast(String(res.message || __('Payment could not be started.')), 'error', 8000);
									return;
								}
								if (!res || !res.order_id || !res.key_id) {
									_paceHideLoading();
									paceShowToast(
										__('Payment session could not be created (missing order or gateway key). Contact support.'),
										'error',
										8000
									);
									return;
								}
								_paceLoadRazorpay(function () {
									_paceHideLoading();
									if (typeof Razorpay === 'undefined') {
										paceShowToast(__('Payment checkout failed to load. Refresh the page and try again.'), 'error');
										return;
									}
									var options = {
										key: res.key_id,
										amount: res.amount,
										currency: res.currency || 'INR',
										order_id: res.order_id,
										name: 'PACE Application Fee',
										description: 'Application Registration Fee',
										prefill: {
											name: (wf.get_value('first_name') || '') + ' ' + (wf.get_value('last_name') || ''),
											email: wf.get_value('email_address') || '',
											contact: wf.get_value('mobile_number') || ''
										},
										theme: { color: '#7B1D1D' },
										handler: function (resp) {
											_paceShowLoading(__('Verifying Payment…'));
											frappe.call({
												method: 'slcm.pace.web_form.pace_application_form.pace_application_form.verify_pace_payment_signature',
												args: {
													razorpay_payment_id: resp.razorpay_payment_id,
													razorpay_order_id: resp.razorpay_order_id,
													razorpay_signature: resp.razorpay_signature,
													assignment_name: res.assignment
												},
												callback: function (vr) {
													_paceHideLoading();
													if (vr.message && vr.message.status === 'success') {
														paceRenderSuccessPage();
													} else {
														var err = (vr.message && vr.message.message) || __('Verification failed.');
														paceShowToast(String(err), 'error', 8000);
													}
												},
												error: function () {
													_paceHideLoading();
													paceShowToast(__('Verification request failed. Please reload or contact support.'), 'error', 8000);
												}
											});
										}
									};
									try {
										var rzp = new Razorpay(options);
										rzp.on('payment.failed', function (failResp) {
											var d = failResp && failResp.error && failResp.error.description;
											paceShowToast(d ? String(d) : __('Payment failed.'), 'error', 8000);
										});
										rzp.open();
									} catch (rzpErr) {
										var rzpMsg = (rzpErr && rzpErr.message) ? String(rzpErr.message) : String(rzpErr);
										paceShowToast(__('Could not open payment window.') + ' ' + rzpMsg, 'error', 8000);
									}
								});
							},
							error: function (xhr) {
								_paceHideLoading();
								var extra = xhr && xhr.responseJSON && xhr.responseJSON._server_messages
									? _paceErrFromCall(xhr.responseJSON)
									: '';
								paceShowToast(extra || __('Could not contact the server to start payment.'), 'error', 8000);
							}
						});
					}, 0);
				});
			},
			error: function () {
				_paceHideLoading();
				paceShowToast(__('Could not load fee. Check your connection and try again.'), 'error');
			}
		});
	}).catch(function (err) {
		_paceHideLoading();
		paceShowToast(
			(err && err.message) ? String(err.message) : __('Could not save application. Check required fields.'),
			'error',
			8000
		);
	});"""

content = content.replace(old_block, new_block)

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

with open(filepath, 'w') as f:
    f.write(content)
