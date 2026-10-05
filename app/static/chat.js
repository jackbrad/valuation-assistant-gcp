// Valuation assistant: chat page. Vanilla JS, no build step.
const $ = (id) => document.getElementById(id);
const money = (n) => '$' + Math.round(n).toLocaleString('en-US');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// [DOC-INS-000014 p.2] or [DOC-A p.2; DOC-B p.1] -> clickable citation chips
const CITE_GROUP = /\[([^\]]*DOC-[^\]]*)\]/g;
const CITE = /(DOC-[A-Z0-9-]+) p\.(\d+)/g;
const citeChip = (doc, page) =>
  `<button type="button" class="cite" data-doc="${doc}" data-page="${page}"><span class="cl-icon">description</span>${doc} p.${page}</button>`;

// Minimal Markdown: paragraphs, bullets, bold, citations. Input is escaped first.
function renderMarkdown(md) {
  const lines = esc(md).split('\n');
  let html = '', inList = false;
  for (const raw of lines) {
    const line = raw.trim();
    const bullet = line.match(/^[*-]\s+(.*)/);
    if (bullet) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += `<li>${bullet[1]}</li>`;
      continue;
    }
    if (inList) { html += '</ul>'; inList = false; }
    if (line) html += `<p>${line}</p>`;
  }
  if (inList) html += '</ul>';
  return html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(CITE_GROUP, (_, inner) => inner.replace(CITE, (__, d, p) => citeChip(d, p)).replace(/[;,]\s*/g, ' '));
}

// Engine reasons -> plain words (numbers are kept exactly as the engine returned them).
function plainReason(r) {
  let m;
  if ((m = r.match(/^Range width ([\d.]+%) exceeds .*threshold \(([\d.]+%)\)/))) return `Comparable sales spread too wide: ${m[1]} (limit ${m[2]})`;
  if ((m = r.match(/is ([\d.]+%) \(exceeds .*threshold ([\d.]+%)\)/))) return `Comparable sales and the price model disagree by ${m[1]} (limit ${m[2]})`;
  if ((m = r.match(/^Insufficient usable comps \((\d+) < minimum required (\d+)\)/))) return `Not enough comparable sales: ${m[1]} found, ${m[2]} needed`;
  if ((m = r.match(/held G1 facts on value-moving fields: (.*)/))) {
    const names = { gla_sqft: 'living area', condition_c: 'condition', quality_q: 'build quality', baths_total: 'bathrooms', beds: 'bedrooms', lot_sqft: 'lot size', year_built: 'year built' };
    return `On hold because sources disagree: ${m[1].split(', ').map((f) => names[f] || f).join(', ')}`;
  }
  return r;
}

function stepSummary(s) {
  const out = (s.output && s.output.result) || s.output || {};
  switch (s.tool) {
    case 'resolve_property': return out.address ? `${out.address} · ${out.property_id}` : 'not found';
    case 'search_documents': return `${(out.results || []).length} passages · ${out.method === 'keyword fallback' ? 'keyword fallback' : 'vector search'}`;
    case 'run_valuation': return out.gate_result === 'shown' ? `${money(out.range_low)} – ${money(out.range_high)}` : 'needs an appraiser';
    case 'get_property_facts': return `${(out.facts || []).length} facts`;
    default: return '';
  }
}

function renderValue(v, address) {
  const card = $('valueCard');
  if (!v) return; // this turn didn't value anything: keep the previous card
  if (v.gate_result === 'shown') {
    card.innerHTML = `
      <div class="value-head">
        <div><div class="cl-card-eyebrow">Valuation engine</div><h2 class="cl-card-title">${esc(address)}</h2></div>
        <span class="cl-badge cl-badge-success"><span class="cl-icon">check_circle</span><span>Value shown</span></span>
      </div>
      <div class="value-range">${money(v.range_low)} – ${money(v.range_high)}</div>
      <div class="value-sub">Point estimate ${money(v.point_estimate)} · confidence ${Math.round(v.confidence_score * 100)}% · ${v.usable_comps_count} comparable sales</div>`;
  } else {
    card.innerHTML = `
      <div class="value-head">
        <div><div class="cl-card-eyebrow">Valuation engine</div><h2 class="cl-card-title">${esc(address)}</h2></div>
        <span class="cl-badge cl-badge-warning"><span class="cl-icon">person_search</span><span>Needs an appraiser</span></span>
      </div>
      <div class="value-sub">No value shown. The engine held it back because:</div>
      <ul class="reasons">${(v.reasons || []).map((r) => `<li>${esc(plainReason(r))}</li>`).join('')}</ul>`;
  }
  card.hidden = false;
}

const signed = (n) => (n >= 0 ? '+' : '−') + money(Math.abs(n));
const pct = (x) => `${Math.round(x * 100)}%`;

function renderDocs(docs) {
  $('docsCard').hidden = !docs.length;
  $('docs').innerHTML = docs.map((d) => {
    const status = d.used.length
      ? `<span class="cl-badge cl-badge-brand"><span class="cl-icon">search</span><span>Used in answer</span></span>`
      : d.is_record
        ? `<span class="cl-badge"><span class="cl-icon">table</span><span>Structured record</span></span>`
        : d.parsed_pages.length
          ? `<span class="cl-badge"><span class="cl-icon">check</span><span>Parsed, not relevant</span></span>`
          : `<span class="cl-badge cl-badge-warning"><span class="cl-icon">schedule</span><span>Not parsed yet</span></span>`;
    const pages = d.parsed_pages.map((p) => citeChip(esc(d.doc_id), p)).join(' ');
    const parse = d.can_ingest
      ? `<button type="button" class="cl-btn cl-btn-primary cl-btn-sm parse-btn" data-doc="${esc(d.doc_id)}" data-address=""><span class="cl-icon">play_arrow</span><span>Parse now</span></button>`
      : '';
    const passages = d.used.map((u) => `
      <div class="passage">
        <div class="passage-head"><span>Page ${u.page}</span>${u.similarity != null ? `<span class="match">match ${u.similarity.toFixed(2)}</span>` : ''}</div>
        <p>${esc(u.text)}</p>
      </div>`).join('');
    return `
      <div class="doc ${d.used.length ? 'doc-used' : ''}">
        <div class="doc-head">
          <span class="cl-icon doc-icon">${d.is_record ? 'table_view' : 'description'}</span>
          <div class="doc-title">
            <div class="doc-type">${esc(d.type)}</div>
            <div class="doc-meta"><span class="code">${esc(d.doc_id)}</span>${d.source ? ' · ' + esc(d.source) : ''}${d.date ? ' · ' + esc(d.date) : ''}</div>
          </div>
          ${status}
        </div>
        ${pages ? `<div class="doc-pages">${pages}</div>` : ''}
        ${parse}
        ${passages}
      </div>`;
  }).join('');
}

function renderIssues(issues) {
  if (!issues || !issues.length) return '';
  return `
    <section class="cl-card section">
      <div><div class="cl-card-eyebrow">Checked by code, not by the model</div>
      <h2 class="cl-card-title">${(() => { const n = issues.filter((i) => i.level !== 'success').length; return n ? `Issues found (${n})` : 'No open issues'; })()}</h2></div>
      ${issues.map((i) => `
        <div class="cl-banner cl-banner-${i.level}">
          <span class="cl-icon">${{ danger: 'error', warning: 'warning', success: 'check_circle' }[i.level] || 'info'}</span>
          <div class="cl-banner-body">
            <div class="cl-banner-title">${esc(i.title)}</div>
            <div class="cl-banner-text">${esc(i.detail)} ${i.cites.map((c) => citeChip(esc(c.doc_id), c.page)).join(' ')}</div>
            ${i.action ? `<div class="issue-action"><strong>Next:</strong> ${esc(i.action)}</div>` : ''}
            ${i.flag ? `<button type="button" class="cl-btn cl-btn-secondary cl-btn-sm flag-btn" data-flag='${esc(JSON.stringify(i.flag))}'><span class="cl-icon">flag</span><span>Flag for correction</span></button>` : ''}
          </div>
        </div>`).join('')}
    </section>`;
}

function processStep(n, title, summary, body, open = false) {
  return `
    <details class="pstep" ${open ? 'open' : ''}>
      <summary>
        <span class="pnum">${n}</span>
        <span class="ptext"><span class="ptitle">${title}</span><span class="psum">${summary}</span></span>
        <span class="cl-icon chev">expand_more</span>
      </summary>
      <div class="pbody">${body}</div>
    </details>`;
}

function renderCalculation(c) {
  if (!c) return '';
  const m = c.method;
  const comps = c.comps;
  const failed = c.checks.filter((k) => !k.ok);

  const step1 = processStep(1, 'Find comparable sales',
    `${m.candidates} recent sales near this house in ${esc(c.submarket)}`,
    `<p>We search arm's-length sales in the same neighborhood from the last ${m.lookback_months} months. We start within ${m.radius_mi[0]} mile and widen to ${m.radius_mi.join(', then ')} miles until there are enough, then rank them by how similar they are (distance, recency, size, quality, condition).</p>`);

  const step2 = processStep(2, 'Adjust for market changes',
    `Each sale price is moved to today using the ${esc(c.submarket)} price index`,
    `<p>Prices drift between the sale date and today (${esc(c.effective_date)}). Each sale is scaled by the change in the neighborhood's monthly median price per sq ft.</p>
     <table class="mini"><thead><tr><th>Sale</th><th>Sold</th><th class="num">Price</th><th class="num">Market change</th></tr></thead><tbody>
     ${comps.map((x) => `<tr><td>${esc(x.address)}</td><td>${esc(x.sale_date)}</td><td class="num">${money(x.sale_price)}</td><td class="num">${signed(x.time_adj)}</td></tr>`).join('')}
     </tbody></table>`);

  const step3 = processStep(3, 'Adjust for differences from this house',
    `Each sale is adjusted to match this house, feature by feature`,
    `<p>If a comparable sale is bigger or better, we subtract the value of that difference; if it's smaller or worse, we add it. The rates are learned from ${esc(c.submarket)} sales.</p>
     <div class="two-col">
       <div><div class="label">This house (county record)</div>
         <table class="mini"><tbody>${c.subject.map((f) => `<tr><td>${esc(f.label)}</td><td class="num">${typeof f.value === 'number' ? f.value.toLocaleString('en-US') : esc(f.value)}${f.unit ? ' ' + f.unit : ''}</td></tr>`).join('')}</tbody></table></div>
       <div><div class="label">Adjustment rates</div>
         <table class="mini"><tbody>${m.rates.map((r) => `<tr><td>${esc(r.label)}</td><td class="num">${esc(r.rate)}</td></tr>`).join('')}</tbody></table></div>
     </div>`);

  const step4 = processStep(4, 'Keep the best matches and weight them',
    `${comps.length} used, ${c.excluded_count} set aside`,
    `${c.excluded_reasons.length ? `<p>Set aside: ${c.excluded_reasons.map(esc).join('; ')}.</p>` : ''}
     <p>Sales that need smaller adjustments get more weight. Click a sale to see its adjustments.</p>
     <div class="comps"><div class="comps-head"><span>Sale</span><span>Adjusted price</span><span>Weight</span></div>${comps.map((x) => `
       <details class="comp">
         <summary>
           <span class="comp-addr">${esc(x.address)}<span class="comp-meta">${x.distance_mi.toFixed(2)} mi · sold ${esc(x.sale_date)}</span></span>
           <span class="num comp-price">${money(x.adjusted_price)}</span>
           <span class="num comp-w">${pct(x.weight)}</span>
         </summary>
         <table class="mini"><tbody>
           <tr><td>Sale price</td><td class="num">${money(x.sale_price)}</td></tr>
           <tr><td>Market change</td><td class="num">${signed(x.time_adj)}</td></tr>
           ${x.adjustments.map((a) => `<tr><td>${esc(a.label)}</td><td class="num">${signed(a.dollars)}</td></tr>`).join('')}
           <tr class="total"><td>Adjusted price</td><td class="num">${money(x.adjusted_price)}</td></tr>
         </tbody></table>
       </details>`).join('')}
     </div>
     <p class="result-line">Weighted average of these sales: <strong>${money(c.sales_comp_value)}</strong></p>`);

  const blended = c.shown
    ? `<strong>${money(c.point)}</strong>, range ${money(c.low)} – ${money(c.high)}`
    : `<strong>withheld</strong> (it failed the checks in step 6)`;
  const step5 = processStep(5, 'Blend with the price model',
    `${pct(c.alpha)} comparable sales + ${pct(1 - c.alpha)} price model`,
    `<p>A second, independent estimate comes from a price model: the neighborhood's median price per sq ft${m.median_ppsf ? ` (${money(m.median_ppsf)})` : ''} times living area, adjusted for bathrooms and condition. Blending the two reduces the risk of one bad method.</p>
     <table class="mini"><tbody>
       <tr><td>Comparable sales</td><td class="num">${money(c.sales_comp_value)} × ${pct(c.alpha)}</td></tr>
       <tr><td>Price model</td><td class="num">${money(c.avm_value)} × ${pct(1 - c.alpha)}</td></tr>
     </tbody></table>
     <p class="result-line">Value: ${blended}</p>`);

  const step6 = processStep(6, 'Run safety checks',
    failed.length ? `${failed.length} of ${c.checks.length} failed, so it goes to an appraiser` : `All ${c.checks.length} passed, so the value is shown`,
    `<p>Before anyone sees a number, the engine checks that the evidence is strong enough. If any check fails, the value is withheld and a licensed appraiser takes over.</p>
     <table class="mini"><thead><tr><th>Check</th><th class="num">Result</th><th class="num">Limit</th><th></th></tr></thead><tbody>
     ${c.checks.map((k) => `<tr><td>${esc(k.label)}</td><td class="num">${esc(k.value)}</td><td class="num">${esc(k.limit)}</td>
       <td class="num">${k.ok ? '<span class="cl-badge cl-badge-success"><span class="cl-icon">check</span><span>Pass</span></span>' : '<span class="cl-badge cl-badge-danger"><span class="cl-icon">close</span><span>Fail</span></span>'}</td></tr>`).join('')}
     </tbody></table>`, true);

  return `
    <section class="cl-card section">
      <div><div class="cl-card-eyebrow">Computed by the valuation engine, not the model</div>
      <h2 class="cl-card-title">How this value was calculated</h2></div>
      <div class="process">${step1}${step2}${step3}${step4}${step5}${step6}</div>
    </section>`;
}

function renderSteps(steps, seconds) {
  if (!steps.length) {
    $('steps').innerHTML = '<li class="no-steps">No tools needed: answered from the conversation.</li>';
    $('stepsCard').hidden = false;
    return;
  }
  $('stepsCard').hidden = false;
  $('steps').innerHTML = steps.map((s, i) => `
    <li><details class="step">
      <summary><span class="num">${i + 1}</span><span class="name">${esc(s.tool)}</span><span class="what">${esc(stepSummary(s))}</span></summary>
      <pre>${esc(JSON.stringify({ args: s.args, output: s.output }, null, 2))}</pre>
    </details></li>`).join('');
}

// The conversation so far. The browser keeps it and sends it with every turn,
// so any server instance can answer a follow-up.
const history = [];
let busy = false;

async function ask(question) {
  if (busy) return;
  busy = true;
  $('start').hidden = true;
  $('result').hidden = false;
  $('newChat').hidden = false;

  const followUp = history.length > 0;
  const thread = $('thread');
  thread.insertAdjacentHTML('beforeend', `<div class="msg-user">${esc(question)}</div>`);
  const bot = document.createElement('div');
  bot.className = 'msg-bot';
  bot.innerHTML = `<div class="avatar"><span class="cl-icon">home_work</span></div>
    <div class="answer"><div class="thinking"><div class="row"><span class="cl-icon spin">progress_activity</span>${followUp ? 'Thinking it through, and checking the documents if needed…' : 'Finding the property, searching its documents and running the valuation…'}</div></div></div>`;
  thread.appendChild(bot);
  bot.scrollIntoView({ behavior: 'smooth', block: 'end' });

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: question, history }),
    });
    if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Server returned ${res.status}`); }
    const data = await res.json();
    bot.querySelector('.answer').innerHTML = renderMarkdown(data.answer || 'No answer returned.')
      + renderIssues(data.issues) + renderCalculation(data.calculation);
    // Panels only change when this turn produced new data for them.
    renderValue(data.valuation, data.property ? data.property.address : '');
    if (data.documents) renderDocs(data.documents);
    renderSteps(data.steps || [], data.seconds);
    $('stepsTurn').textContent = followUp ? 'for your last question' : '';
    $('metaLine').textContent = data.replayed
      ? `Replayed answer saved ${data.replayed.saved_at} · live call failed`
      : `${data.model} · ${data.steps.length} tool call${data.steps.length === 1 ? '' : 's'} · ${data.seconds} s`;
    if (data.replayed) {
      bot.querySelector('.answer').insertAdjacentHTML('afterbegin',
        `<div class="cl-banner cl-banner-warning replay"><span class="cl-icon">history</span><div class="cl-banner-body"><div class="cl-banner-text">Gemini didn't respond, so this is the saved answer from ${esc(data.replayed.saved_at)}. Same question, same data.</div></div></div>`);
    }
    history.push({ role: 'user', text: question }, { role: 'model', text: data.answer || '' });
  } catch (e) {
    bot.querySelector('.answer').innerHTML = `<p class="error">Something went wrong: ${esc(e.message)}. Try again.</p>`;
  } finally {
    busy = false;
  }
}

// Live ingestion: stream each pipeline step into a card in the conversation
const STEP_ICONS = { fetch: 'cloud_download', layout: 'view_quilt', extract: 'data_object', gate: 'verified_user', embed: 'hub', store: 'database' };

async function parseDocument(docId) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('.parse-btn').forEach((b) => { b.disabled = true; });
  const card = document.createElement('div');
  card.className = 'msg-bot';
  card.innerHTML = `<div class="avatar"><span class="cl-icon">conveyor_belt</span></div>
    <div class="answer"><section class="cl-card section ingest">
      <div><div class="cl-card-eyebrow">Ingestion pipeline · live</div><h2 class="cl-card-title">Parsing ${esc(docId)}</h2></div>
      <ol class="ingest-steps"></ol>
      <div class="ingest-result"></div>
    </section></div>`;
  $('thread').appendChild(card);
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  const list = card.querySelector('.ingest-steps');
  const rows = {};
  const started = Date.now();

  const render = (ev) => {
    let li = rows[ev.step];
    if (!li) { li = document.createElement('li'); rows[ev.step] = li; list.appendChild(li); }
    const icon = ev.status === 'running' ? '<span class="cl-icon spin">progress_activity</span>'
      : ev.status === 'error' ? '<span class="cl-icon bad">error</span>'
      : `<span class="cl-icon ok">${ev.step === 'gate' && ev.held && ev.held.length ? 'gpp_maybe' : 'check_circle'}</span>`;
    const facts = ev.facts && ev.facts.length
      ? `<div class="ingest-facts">${ev.facts.map((f) => `<span class="cl-badge"><span class="code">${esc(f.field)}</span>&nbsp;= ${esc(f.value)} · p.${f.page}</span>`).join(' ')}</div>` : '';
    const held = ev.held && ev.held.length
      ? `<div class="ingest-facts">${ev.held.map((h) => `<span class="cl-badge cl-badge-warning"><span class="cl-icon">pause_circle</span><span>${esc(h.field)}: record ${esc(h.record)} vs document ${esc(h.document)} · held</span></span>`).join(' ')}</div>` : '';
    li.className = `ingest-step ${ev.status}`;
    li.innerHTML = `${icon}<div class="ingest-text"><div class="ingest-title"><span class="cl-icon step-icon">${STEP_ICONS[ev.step] || 'circle'}</span>${esc(ev.title || ev.step)}${ev.seconds != null ? `<span class="ingest-time">${ev.seconds} s</span>` : ''}</div>
      <div class="ingest-detail">${esc(ev.detail || '')}</div>${facts}${held}</div>`;
  };

  try {
    const res = await fetch(`/api/ingest/${encodeURIComponent(docId)}`, { method: 'POST' });
    if (!res.ok || !res.body) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Server returned ${res.status}`); }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let done = null;
    for (;;) {
      const { value, done: finished } = await reader.read();
      if (finished) break;
      buffer += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.step === 'complete') done = ev;
        else if (ev.step === 'error') throw new Error(ev.detail);
        else render(ev);
      }
    }
    if (!done) throw new Error('The pipeline stopped before finishing.');
    const total = ((Date.now() - started) / 1000).toFixed(1);
    const q = `What is ${done.address} worth now?`;
    card.querySelector('.ingest-result').innerHTML = `
      <div class="cl-banner ${done.held.length ? 'cl-banner-warning' : 'cl-banner-success'}">
        <span class="cl-icon">${done.held.length ? 'gpp_maybe' : 'check_circle'}</span>
        <div class="cl-banner-body"><div class="cl-banner-text">
          Parsed in ${total} s and searchable now.
          ${done.held.length ? `The data check held ${done.held.length === 1 ? 'one fact' : done.held.length + ' facts'} that disagree${done.held.length === 1 ? 's' : ''} with the county record, so it went to the review queue instead of into the value.` : ''}
        </div></div>
      </div>
      <button type="button" class="cl-btn cl-btn-primary ask-again" data-q="${esc(q)}"><span class="cl-icon">forum</span><span>Ask: ${esc(q)}</span></button>`;
    $('docsCard').querySelectorAll('.parse-btn').forEach((b) => b.remove());
    refreshQueueCount();
  } catch (e) {
    card.querySelector('.ingest-result').innerHTML = `<p class="error">Ingestion failed: ${esc(e.message)}</p>`;
    document.querySelectorAll('.parse-btn').forEach((b) => { b.disabled = false; });
  } finally {
    busy = false;
  }
}

async function refreshQueueCount() {
  // Keep the nav badge honest after the data gate opens a review item.
  try {
    const html = await (await fetch('/review')).text();
    const m = html.match(/Waiting for review <span class="muted">\((\d+)\)/);
    const link = document.querySelector('.nav-link[href="/review"]');
    if (!m || !link) return;
    let badge = link.querySelector('.count');
    if (!badge) { badge = document.createElement('span'); badge.className = 'cl-badge cl-badge-new count'; link.appendChild(badge); }
    badge.textContent = m[1];
  } catch (e) {}
}

document.addEventListener('click', (e) => {
  const p = e.target.closest('.parse-btn');
  if (p) { parseDocument(p.dataset.doc); return; }
  const again = e.target.closest('.ask-again');
  if (again) { again.disabled = true; ask(again.dataset.q); }
});

// Flag drawer
document.addEventListener('click', (e) => {
  const btn = e.target.closest('.flag-btn');
  if (btn) {
    const f = JSON.parse(btn.dataset.flag);
    $('flagProperty').value = f.property_id;
    $('flagField').value = f.field;
    $('flagEvidence').value = f.evidence;
    $('flagLabel').textContent = f.label;
    $('flagCurrent').textContent = f.current;
    $('flagCites').innerHTML = (f.evidence.match(/DOC-[A-Z0-9-]+ p\.\d+/g) || [])
      .map((c) => { const [d, p] = c.split(' p.'); return citeChip(d, p); }).join(' ');
    $('flagDrawer').hidden = false;
    $('flagValue').focus();
    return;
  }
  if (e.target.closest('[data-close]') || e.target === $('flagDrawer')) $('flagDrawer').hidden = true;
});

// Wiring
$('askForm').addEventListener('submit', (e) => { e.preventDefault(); const q = $('askInput').value.trim(); if (q) ask(q); });
$('followForm').addEventListener('submit', (e) => { e.preventDefault(); const q = $('followInput').value.trim(); if (q) { $('followInput').value = ''; ask(q); } });
for (const id of ['askInput', 'followInput']) {
  $(id).addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.target.form.requestSubmit(); } });
}
document.querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => ask(c.dataset.q)));
$('newChat').addEventListener('click', () => { window.location.href = '/'; });

// Deep link: /?q=... asks straight away
const preset = new URLSearchParams(location.search).get('q');
if (preset) ask(preset);
