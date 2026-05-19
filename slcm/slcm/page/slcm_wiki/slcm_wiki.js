frappe.pages['slcm-wiki'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'SLCM Wiki',
		single_column: true,
	});

	const $body = $(wrapper).find('.page-content');
	$body.css({ padding: '0', background: '#0f172a' });

	// ── Inject styles ─────────────────────────────────────────────────────────
	if (!document.getElementById('wiki-styles')) {
		$(`<style id="wiki-styles">
		@media print {
			.wiki-topbar, .wiki-sidebar, .wiki-print-hide { display:none !important; }
			.wiki-wrap { display:block !important; }
			.wiki-content { margin:0 !important; padding:20px !important; background:#fff !important; color:#000 !important; box-shadow:none !important; border-radius:0 !important; }
			.wiki-content h1,.wiki-content h2,.wiki-content h3 { color:#000 !important; border-color:#ccc !important; }
			.wiki-content code,.wiki-content pre { background:#f5f5f5 !important; color:#333 !important; border:1px solid #ddd !important; }
			.wiki-content table th { background:#eee !important; color:#000 !important; }
			.wiki-content a { color:#000 !important; text-decoration:none !important; }
			body { background:#fff !important; }
		}

		.wiki-wrap { font-family:'Inter','Segoe UI',sans-serif; background:#0f172a; color:#e2e8f0; min-height:100vh; display:flex; flex-direction:column; }

		/* Top bar */
		.wiki-topbar {
			background:#1e293b; border-bottom:1px solid #334155;
			padding:14px 32px; display:flex; align-items:center; gap:14px;
			position:sticky; top:0; z-index:100;
		}
		.wiki-topbar-icon { width:38px; height:38px; background:linear-gradient(135deg,#3b82f6,#8b5cf6); border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:18px; flex-shrink:0; }
		.wiki-topbar-title { font-size:16px; font-weight:800; color:#f1f5f9; }
		.wiki-topbar-sub   { font-size:11px; color:#64748b; margin-top:1px; }
		.wiki-btn-group    { margin-left:auto; display:flex; gap:8px; align-items:center; }

		.wiki-btn {
			display:inline-flex; align-items:center; gap:6px;
			padding:8px 16px; border-radius:8px; font-size:12px; font-weight:600;
			cursor:pointer; border:1.5px solid #334155; background:#0f172a;
			color:#94a3b8; transition:all .15s; white-space:nowrap;
		}
		.wiki-btn:hover { background:#1e293b; color:#e2e8f0; border-color:#475569; }
		.wiki-btn.primary { background:#1e3a5f; color:#60a5fa; border-color:#3b82f6; }
		.wiki-btn.primary:hover { background:#2563eb; color:#fff; }
		.wiki-btn.success { background:#064e3b; color:#34d399; border-color:#059669; }
		.wiki-btn.success:hover { background:#059669; color:#fff; }
		.wiki-btn.purple  { background:#2e1065; color:#c4b5fd; border-color:#7c3aed; }
		.wiki-btn.purple:hover  { background:#7c3aed; color:#fff; }

		/* Body */
		.wiki-body { display:flex; flex:1; overflow:hidden; }

		/* Sidebar TOC */
		.wiki-sidebar {
			width:240px; flex-shrink:0; background:#1e293b; border-right:1px solid #334155;
			padding:20px 0; overflow-y:auto; height:calc(100vh - 60px);
			position:sticky; top:60px;
		}
		.wiki-toc-title { font-size:10px; font-weight:700; color:#475569; text-transform:uppercase; letter-spacing:1px; padding:0 18px 10px; }
		.wiki-toc-item {
			display:block; padding:7px 18px; font-size:12px; color:#64748b;
			text-decoration:none; cursor:pointer; border-left:2px solid transparent;
			transition:all .15s; line-height:1.4;
		}
		.wiki-toc-item:hover { color:#e2e8f0; background:#263348; border-left-color:#475569; }
		.wiki-toc-item.active { color:#60a5fa; background:#1a2f4a; border-left-color:#3b82f6; font-weight:600; }
		.wiki-toc-item.h2 { padding-left:28px; font-size:11px; }
		.wiki-toc-item.h3 { padding-left:38px; font-size:11px; color:#475569; }

		/* Main content */
		.wiki-main { flex:1; overflow-y:auto; padding:32px 40px 80px; }

		.wiki-content {
			max-width:880px; margin:0 auto;
			background:#1e293b; border-radius:16px; padding:40px 48px;
			border:1px solid #334155; box-shadow:0 4px 24px rgba(0,0,0,.3);
		}

		/* Typography */
		.wiki-content h1 { font-size:28px; font-weight:800; color:#f1f5f9; border-bottom:2px solid #334155; padding-bottom:12px; margin:0 0 24px; }
		.wiki-content h2 { font-size:20px; font-weight:700; color:#e2e8f0; border-bottom:1px solid #1e293b; padding-bottom:8px; margin:36px 0 16px; }
		.wiki-content h2:first-child { margin-top:0; }
		.wiki-content h3 { font-size:15px; font-weight:700; color:#cbd5e1; margin:24px 0 10px; }
		.wiki-content h4 { font-size:13px; font-weight:700; color:#94a3b8; margin:18px 0 8px; text-transform:uppercase; letter-spacing:.5px; }
		.wiki-content p  { font-size:14px; color:#94a3b8; line-height:1.75; margin:0 0 14px; }
		.wiki-content ul,.wiki-content ol { padding-left:24px; margin:0 0 14px; }
		.wiki-content li { font-size:14px; color:#94a3b8; line-height:1.75; margin-bottom:4px; }
		.wiki-content strong { color:#cbd5e1; font-weight:700; }
		.wiki-content em { color:#94a3b8; font-style:italic; }
		.wiki-content hr { border:none; border-top:1px solid #334155; margin:28px 0; }
		.wiki-content a  { color:#60a5fa; text-decoration:none; }
		.wiki-content a:hover { text-decoration:underline; }
		.wiki-content blockquote { border-left:3px solid #3b82f6; padding:8px 16px; background:#0f172a; border-radius:0 8px 8px 0; margin:12px 0; color:#64748b; font-size:13px; }

		/* Code */
		.wiki-content code { background:#0f172a; color:#34d399; padding:2px 7px; border-radius:5px; font-size:12px; font-family:'Fira Code','Courier New',monospace; border:1px solid #1e293b; }
		.wiki-content pre  { background:#0f172a; border:1px solid #334155; border-radius:10px; padding:16px 20px; overflow-x:auto; margin:14px 0; }
		.wiki-content pre code { background:none; border:none; color:#5eead4; padding:0; font-size:12px; line-height:1.7; }

		/* Tables */
		.wiki-content table { width:100%; border-collapse:collapse; margin:16px 0; font-size:13px; }
		.wiki-content th { background:#0f172a; color:#60a5fa; padding:10px 14px; text-align:left; font-weight:700; border:1px solid #334155; font-size:11px; text-transform:uppercase; letter-spacing:.5px; }
		.wiki-content td { padding:9px 14px; border:1px solid #1e293b; color:#94a3b8; vertical-align:top; line-height:1.6; }
		.wiki-content tr:nth-child(even) td { background:#161f2e; }
		.wiki-content tr:hover td { background:#1a2a3a; }

		/* Module section highlight */
		.wiki-content h2[data-module] { background:linear-gradient(90deg,#1e3a5f22,transparent); padding:10px 14px; border-radius:8px 8px 0 0; border-left:3px solid #3b82f6; border-bottom:1px solid #334155; }

		/* Loading */
		.wiki-loading { display:flex; flex-direction:column; align-items:center; justify-content:center; height:300px; gap:16px; color:#475569; }
		.wiki-spinner { width:36px; height:36px; border:3px solid #1e293b; border-top-color:#3b82f6; border-radius:50%; animation:wspin .8s linear infinite; }
		@keyframes wspin { to { transform:rotate(360deg); } }

		/* Search highlight */
		mark { background:#fbbf2444; color:#fbbf24; border-radius:3px; padding:1px 3px; }

		/* Search box */
		.wiki-search { display:flex; align-items:center; gap:8px; background:#0f172a; border:1.5px solid #334155; border-radius:8px; padding:6px 12px; }
		.wiki-search input { background:none; border:none; outline:none; color:#e2e8f0; font-size:12px; width:160px; }
		.wiki-search input::placeholder { color:#475569; }
		</style>`).appendTo('head');
	}

	// ── Build skeleton ────────────────────────────────────────────────────────
	$body.html(`
	<div class="wiki-wrap">
	  <div class="wiki-topbar">
	    <div class="wiki-topbar-icon">📖</div>
	    <div>
	      <div class="wiki-topbar-title">SLCM v16 — Wiki</div>
	      <div class="wiki-topbar-sub">Complete module documentation</div>
	    </div>
	    <div class="wiki-btn-group wiki-print-hide">
	      <div class="wiki-search">
	        <span style="color:#475569;font-size:13px;">🔍</span>
	        <input type="text" id="wiki-search-input" placeholder="Search wiki..." oninput="wikiSearch(this.value)" />
	      </div>
	      <button class="wiki-btn primary" onclick="wikiDownloadMD()">⬇ Download MD</button>
	      <button class="wiki-btn success" onclick="wikiDownloadPDF()">🖨 Download PDF</button>
	      <button class="wiki-btn purple"  onclick="wikiDownloadHTML()">📄 Download HTML</button>
	    </div>
	  </div>
	  <div class="wiki-body">
	    <div class="wiki-sidebar" id="wiki-toc">
	      <div class="wiki-toc-title">Contents</div>
	      <div id="wiki-toc-list"></div>
	    </div>
	    <div class="wiki-main">
	      <div class="wiki-content" id="wiki-rendered">
	        <div class="wiki-loading">
	          <div class="wiki-spinner"></div>
	          <div>Loading wiki…</div>
	        </div>
	      </div>
	    </div>
	  </div>
	</div>
	`);

	// ── Load wiki content ─────────────────────────────────────────────────────
	frappe.call({
		method: 'slcm.slcm.page.slcm_wiki.slcm_wiki.get_wiki_content',
		callback: function(r) {
			if (r.message) {
				window._wikiRawMD = r.message;
				const html = wikiMdToHtml(r.message);
				document.getElementById('wiki-rendered').innerHTML = html;
				wikiBuildTOC();
				wikiScrollSpy();
			} else {
				document.getElementById('wiki-rendered').innerHTML =
					'<p style="color:#f87171;padding:40px;">Wiki file not found. Please ensure docs/SLCM_WIKI.md exists in the project root.</p>';
			}
		}
	});

	// ── Markdown → HTML renderer ──────────────────────────────────────────────
	window.wikiMdToHtml = function(md) {
		let html = md
			// Escape HTML entities in code blocks first
			.replace(/```([\s\S]*?)```/g, (_, code) =>
				`<pre><code>${code.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</code></pre>`)
			// Inline code
			.replace(/`([^`]+)`/g, '<code>$1</code>')
			// HR
			.replace(/^---$/gm, '<hr>')
			// H1
			.replace(/^# (.+)$/gm, '<h1>$1</h1>')
			// H2
			.replace(/^## (.+)$/gm, (_, t) => `<h2 id="h-${t.replace(/[^a-z0-9]/gi,'-').toLowerCase()}">${t}</h2>`)
			// H3
			.replace(/^### (.+)$/gm, (_, t) => `<h3 id="h3-${t.replace(/[^a-z0-9]/gi,'-').toLowerCase()}">${t}</h3>`)
			// H4
			.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
			// Bold
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
			// Italic
			.replace(/\*(.+?)\*/g, '<em>$1</em>')
			// Blockquote
			.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
			// Tables
			.replace(/^(\|.+\|)\n\|[-| :]+\|\n((?:\|.+\|\n?)+)/gm, (_, header, rows) => {
				const ths = header.split('|').filter(c=>c.trim()).map(c=>`<th>${c.trim()}</th>`).join('');
				const trs = rows.trim().split('\n').map(row => {
					const tds = row.split('|').filter(c=>c.trim()).map(c=>`<td>${c.trim()}</td>`).join('');
					return `<tr>${tds}</tr>`;
				}).join('');
				return `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
			})
			// Unordered list
			.replace(/^([ \t]*[-*] .+\n?)+/gm, block => {
				const items = block.trim().split('\n').map(l => `<li>${l.replace(/^[ \t]*[-*] /,'')}</li>`).join('');
				return `<ul>${items}</ul>`;
			})
			// Ordered list
			.replace(/^([ \t]*\d+\. .+\n?)+/gm, block => {
				const items = block.trim().split('\n').map(l => `<li>${l.replace(/^[ \t]*\d+\. /,'')}</li>`).join('');
				return `<ol>${items}</ol>`;
			})
			// Links
			.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
			// Paragraphs (lines not already wrapped)
			.replace(/^(?!<[a-z]|$)(.+)$/gm, '<p>$1</p>');

		return html;
	};

	// ── Build TOC from H2/H3 ──────────────────────────────────────────────────
	window.wikiBuildTOC = function() {
		const headings = document.querySelectorAll('#wiki-rendered h1, #wiki-rendered h2, #wiki-rendered h3');
		const toc = document.getElementById('wiki-toc-list');
		toc.innerHTML = '';
		headings.forEach(h => {
			const level = h.tagName.toLowerCase();
			const item  = document.createElement('a');
			item.className = `wiki-toc-item ${level === 'h3' ? 'h3' : level === 'h2' ? 'h2' : ''}`;
			item.textContent = h.textContent;
			item.onclick = () => { h.scrollIntoView({ behavior:'smooth', block:'start' }); };
			toc.appendChild(item);
		});
	};

	// ── Scroll spy ────────────────────────────────────────────────────────────
	window.wikiScrollSpy = function() {
		const main = document.querySelector('.wiki-main');
		if (!main) return;
		main.addEventListener('scroll', () => {
			const headings = [...document.querySelectorAll('#wiki-rendered h1, #wiki-rendered h2, #wiki-rendered h3')];
			const tocItems = [...document.querySelectorAll('#wiki-toc-list .wiki-toc-item')];
			const scrollTop = main.scrollTop + 80;
			let current = 0;
			headings.forEach((h, i) => { if (h.offsetTop <= scrollTop) current = i; });
			tocItems.forEach((t, i) => t.classList.toggle('active', i === current));
		});
	};

	// ── Search ────────────────────────────────────────────────────────────────
	window.wikiSearch = function(query) {
		const content = document.getElementById('wiki-rendered');
		if (!query.trim()) {
			content.innerHTML = wikiMdToHtml(window._wikiRawMD);
			wikiBuildTOC();
			return;
		}
		const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
		const regex   = new RegExp(`(${escaped})`, 'gi');
		const html    = wikiMdToHtml(window._wikiRawMD);
		content.innerHTML = html.replace(regex, '<mark>$1</mark>');
	};

	// ── Download MD ───────────────────────────────────────────────────────────
	window.wikiDownloadMD = function() {
		if (!window._wikiRawMD) { frappe.msgprint('Wiki content not loaded yet.'); return; }
		const blob = new Blob([window._wikiRawMD], { type: 'text/markdown' });
		const url  = URL.createObjectURL(blob);
		const a    = document.createElement('a');
		a.href     = url;
		a.download = 'SLCM_WIKI.md';
		a.click();
		URL.revokeObjectURL(url);
		frappe.show_alert({ message: 'SLCM_WIKI.md downloaded!', indicator: 'green' });
	};

	// ── Download PDF ──────────────────────────────────────────────────────────
	window.wikiDownloadPDF = function() {
		frappe.show_alert({ message: 'Opening print dialog — choose "Save as PDF"', indicator: 'blue' });
		setTimeout(() => window.print(), 400);
	};

	// ── Download HTML ─────────────────────────────────────────────────────────
	window.wikiDownloadHTML = function() {
		if (!window._wikiRawMD) { frappe.msgprint('Wiki content not loaded yet.'); return; }
		const content = wikiMdToHtml(window._wikiRawMD);
		const full = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>SLCM v16 Wiki</title>
<style>
  body { font-family:'Segoe UI',sans-serif; max-width:900px; margin:40px auto; padding:0 24px 80px; color:#1e293b; background:#fff; }
  h1 { font-size:28px; font-weight:800; color:#0f172a; border-bottom:2px solid #e2e8f0; padding-bottom:12px; margin:0 0 24px; }
  h2 { font-size:20px; font-weight:700; color:#1e293b; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin:36px 0 16px; }
  h3 { font-size:16px; font-weight:700; color:#334155; margin:24px 0 10px; }
  h4 { font-size:13px; font-weight:700; color:#475569; margin:18px 0 8px; text-transform:uppercase; letter-spacing:.5px; }
  p  { font-size:14px; color:#475569; line-height:1.75; margin:0 0 14px; }
  ul,ol { padding-left:24px; margin:0 0 14px; }
  li { font-size:14px; color:#475569; line-height:1.75; margin-bottom:4px; }
  code { background:#f1f5f9; color:#0891b2; padding:2px 6px; border-radius:4px; font-size:12px; border:1px solid #e2e8f0; }
  pre  { background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; overflow-x:auto; margin:14px 0; }
  pre code { background:none; border:none; color:#0f766e; }
  table { width:100%; border-collapse:collapse; margin:16px 0; font-size:13px; }
  th { background:#f1f5f9; color:#1e293b; padding:10px 14px; text-align:left; font-weight:700; border:1px solid #e2e8f0; }
  td { padding:9px 14px; border:1px solid #e2e8f0; color:#475569; }
  tr:nth-child(even) td { background:#f8fafc; }
  hr { border:none; border-top:1px solid #e2e8f0; margin:28px 0; }
  blockquote { border-left:3px solid #3b82f6; padding:8px 16px; background:#eff6ff; border-radius:0 8px 8px 0; margin:12px 0; color:#475569; }
  strong { color:#1e293b; }
  a { color:#2563eb; }
</style>
</head>
<body>${content}</body>
</html>`;
		const blob = new Blob([full], { type: 'text/html' });
		const url  = URL.createObjectURL(blob);
		const a    = document.createElement('a');
		a.href     = url;
		a.download = 'SLCM_WIKI.html';
		a.click();
		URL.revokeObjectURL(url);
		frappe.show_alert({ message: 'SLCM_WIKI.html downloaded!', indicator: 'green' });
	};
};
