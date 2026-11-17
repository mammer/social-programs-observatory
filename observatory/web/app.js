/* Social programmes observatory — single-page front end.
   To add a page: write a function in PAGES that builds DOM nodes, and add it to NAV. */
(function () {
  const state = {lang: 'en', user: null, role: null, page: 'home', cache: {}};
  try { state.lang = localStorage.getItem('obs_lang') || 'en'; } catch (e) { /* storage off */ }

  /* ---------- helpers */
  const t = k => (I18N[state.lang] && I18N[state.lang][k]) ?? I18N.en[k] ?? k;
  const nf = () => new Intl.NumberFormat(state.lang === 'en' ? 'en-GB' : 'fr-FR');
  const int = v => v == null ? '—' : nf().format(Math.round(v));
  const pct = (v, d = 0) => v == null ? '—' : (v * 100).toFixed(d).replace('.', state.lang === 'en' ? '.' : ',') + ' %';
  const dec = (v, d = 2) => v == null ? '—' : Number(v).toFixed(d).replace('.', state.lang === 'en' ? '.' : ',');

  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') e.className = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) e.append(kid instanceof Node ? kid : String(kid));
    return e;
  }
  const pill = (cls, text) => h('span', {class: 'pill ' + cls}, text);
  const tile = (label, value, cls) => h('div', {class: 'tile ' + (cls || '')}, h('span', {class: 'lab'}, label), h('span', {class: 'big'}, value));
  const table = (heads, rows) => h('div', {class: 'tablewrap'}, h('table', {},
    h('thead', {}, h('tr', {}, heads.map(x => h('th', {}, x)))),
    h('tbody', {}, rows.map(cells => h('tr', {}, cells.map(c => h('td', {class: c && c.wrap ? 'wrap' : null}, c && c.node ? c.node : c)))))));
  const section = (title, cap, ...body) => h('section', {}, h('h2', {}, title), cap ? h('p', {class: 'cap'}, cap) : null, ...body);
  const chartBox = draw => { const d = h('div', {class: 'chart'}); requestAnimationFrame(() => draw(d)); return d; };
  const status = {
    cov: v => v >= .85 ? 'ok' : v >= .7 ? 'warn' : 'bad',
    fna: (v, n) => v / n <= .03 ? 'ok' : v / n <= .08 ? 'warn' : 'bad',
    vv: (v, p) => v == null ? 'na' : Math.abs(v - p) > .15 ? 'bad' : Math.abs(v - p) > .07 ? 'warn' : 'ok',
    gap: v => v == null ? 'na' : v < -1 ? 'bad' : v < -.5 ? 'warn' : 'ok', comp: v => v >= .95 ? 'ok' : v >= .85 ? 'warn' : 'bad'
  };

  async function api(path, opts) {
    if (!opts && state.cache[path]) return state.cache[path];
    const r = await fetch(path, Object.assign({credentials: 'same-origin', headers: {'Content-Type': 'application/json'}}, opts || {}));
    if (r.status === 401) { showLogin(); throw new Error('login'); }
    const body = await r.json();
    if (!r.ok) throw Object.assign(new Error(body.error || 'error'), {body, status: r.status});
    if (!opts) state.cache[path] = body;
    return body;
  }
  const data = (group, name) => api(`/api/data/${group}/${name}`);
  const kv = rows => Object.fromEntries(rows.map(r => [r.metric, r.value]));

  /* ---------- language */
  function setLang(lang) {
    state.lang = lang;
    try { localStorage.setItem('obs_lang', lang); } catch (e) { /* ignore */ }
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    document.querySelectorAll('[data-i18n]').forEach(e => { e.textContent = t(e.dataset.i18n); });
    document.querySelectorAll('.langs').forEach(box => {
      box.replaceChildren(...[['en', 'EN'], ['fr', 'FR'], ['ar', 'ع']].map(([k, lab]) =>
        h('button', {type: 'button', 'aria-pressed': String(k === lang), onclick: () => setLang(k)}, lab)));
    });
    if (state.user) { renderNav(); render(); }
  }

  /* ---------- auth */
  function showLogin() { document.getElementById('shell').hidden = true; document.getElementById('login').hidden = false; document.getElementById('u').focus(); }
  document.getElementById('login-form').addEventListener('submit', async ev => {
    ev.preventDefault();
    const err = document.getElementById('login-error'); err.hidden = true;
    try {
      const me = await api('/api/login', {method: 'POST', body: JSON.stringify({username: ev.target.username.value, password: ev.target.password.value})});
      ev.target.password.value = '';
      start(me);
    } catch (e) { if (e.message !== 'login') err.hidden = false; }
  });
  document.getElementById('logout').addEventListener('click', async () => {
    await fetch('/api/logout', {method: 'POST', credentials: 'same-origin'});
    state.user = null; state.cache = {}; showLogin();
  });

  function start(me) {
    state.user = me.user; state.role = me.role;
    document.getElementById('login').hidden = true; document.getElementById('shell').hidden = false;
    document.getElementById('who').textContent = `${me.user} · ${me.role}`;
    renderNav(); render();
  }

  /* ---------- navigation */
  const NAV = [['home', 'nav_home'], ['aid', 'nav_aid'], ['models', 'nav_models'], ['data', 'nav_data']];
  function renderNav() {
    document.getElementById('nav').replaceChildren(...NAV.map(([id, key]) =>
      h('a', {href: '#' + id, 'aria-current': state.page === id ? 'page' : null}, t(key))));
  }
  window.addEventListener('hashchange', () => { state.page = (location.hash || '#home').slice(1); if (state.user) { renderNav(); render(); } });

  async function render() {
    const main = document.getElementById('main');
    const fn = PAGES[state.page] || PAGES.home;
    main.replaceChildren(h('p', {class: 'muted'}, '…'));
    try { main.replaceChildren(...[].concat(await fn())); }
    catch (e) {
      if (e.message === 'login') return;
      main.replaceChildren(h('div', {class: 'notice warn'}, e.body && e.body.error === 'not_imported' ? t('not_imported') : t('fail') + ' (' + e.message + ')'));
    }
  }
  let rz; window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => state.user && render(), 250); });

  /* ---------- pages */
  const PAGES = {
    async home() {
      const a = kv(await data('stats', 'kpis'));
      const mod = (id, title, text) => h('a', {class: 'module', href: '#' + id}, h('h3', {}, title), h('p', {class: 'muted'}, text));
      return [
        h('div', {class: 'page-head'}, h('p', {class: 'eyebrow'}, t('subtitle')), h('h1', {}, t('app_title')), h('p', {class: 'muted'}, t('home_lead'))),
        h('div', {class: 'tiles'},
          tile(t('households'), int(a.records)), tile(t('reached'), pct(a.any_aid / a.records, 1), 'ok'),
          tile(t('multi'), int(a.multi_aid), 'warn'), tile(t('fragile_nc'), int(a.fragile_no_cover), 'bad')),
        h('div', {class: 'modules'}, mod('aid', t('nav_aid'), t('m_aid')), mod('models', t('nav_models'), t('m_models')), mod('data', t('nav_data'), t('m_data')))
      ];
    },

    async aid() {
      const [k, programs, areas, gender, combos, lor, profile, daily] = await Promise.all([
        data('stats', 'kpis'), data('stats', 'programs'), data('stats', 'areas'), data('stats', 'gender'), data('stats', 'combos'),
        data('stats', 'lorenz'), data('stats', 'profile'), data('stats', 'daily')]);
      const a = kv(k), overall = a.vv_share;
      let dim = 'social';
      const profBox = h('div', {class: 'chart'});
      const ordered = ['age', 'household', 'programs'];
      const drawProfile = () => {
        const rows = profile.filter(r => r.dimension === dim);
        if (!ordered.includes(dim)) rows.sort((x, y) => y.households - x.households);
        const tot = rows.reduce((s, r) => s + r.households, 0);
        Charts.bars(profBox, rows.map(r => ({label: ordered.includes(dim) ? String(r.category) : t(r.category), value: r.households, text: `${int(r.households)} · ${pct(r.households / tot)}`})));
      };
      requestAnimationFrame(drawProfile);
      const dims = ['social', 'health', 'coverage', 'sector', 'family', 'sex', 'age', 'household', 'programs'];
      return [
        h('div', {class: 'page-head'}, h('h1', {}, t('nav_aid')), h('p', {class: 'muted'}, t('m_aid'))),
        h('div', {class: 'tiles'}, tile(t('households'), int(a.records)), tile(t('reached'), pct(a.any_aid / a.records, 1), 'ok'),
          tile(t('multi'), int(a.multi_aid), 'warn'), tile(t('fragile_nc'), int(a.fragile_no_cover), 'bad'), tile(t('no_aid'), int(a.no_aid), 'bad')),
        section(t('areas_alerts'), t('areas_cap'), table(
          [t('area'), t('households'), t('coverage'), t('fragile_no_aid'), t('vv'), t('gap'), t('completeness')],
          areas.map(r => {
            const cov = r.any_aid / r.households, vv = r.assessed ? r.very_vuln / r.assessed : null;
            return [r.area, int(r.households), {node: pill(status.cov(cov), pct(cov, 1))}, {node: pill(status.fna(r.fragile_no_aid, r.households), int(r.fragile_no_aid))},
              {node: vv == null ? pill('na', t('not_assessed')) : pill(status.vv(vv, overall), pct(vv))},
              {node: r.gap == null ? pill('na', '—') : pill(status.gap(r.gap), (r.gap > 0 ? '+' : '') + dec(r.gap))},
              {node: pill(status.comp(r.completeness), pct(r.completeness))}];
          }))),
        h('div', {class: 'grid2'},
          h('div', {class: 'card'}, h('h3', {}, t('programs')), chartBox(d => Charts.bars(d, programs.map(r => ({label: t(r.program), value: r.households, text: int(r.households)}))))),
          h('div', {class: 'card'}, h('h3', {}, t('daily')), chartBox(d => Charts.columns(d, daily.map(r => ({date: r.date, value: r.households})))))),
        h('div', {class: 'grid2'},
          h('div', {class: 'card'}, h('h3', {}, t('combos')), chartBox(d => Charts.bars(d, combos.map(r => ({label: r.combo.split('+').map(t).join(' + '), value: r.households, text: int(r.households)}))))),
          h('div', {class: 'card'}, h('h3', {}, t('lorenz')), h('p', {class: 'cap'}, `${t('gini')}: ${dec(a.gini, 3)}`), chartBox(d => Charts.lorenz(d, lor)))),
        section(t('gender'), null, table([t('group'), t('households'), t('aid_any'), t('multi_short'), t('vv'), t('no_cover')],
          gender.map(r => [t(r.group), int(r.households), pct(r.aid_any), pct(r.multi), pct(r.very_vulnerable), pct(r.no_cover)]))),
        section(t('profile'), null,
          h('div', {class: 'ctrl'}, h('label', {}, t('show'), h('select', {onchange: ev => { dim = ev.target.value; drawProfile(); }}, dims.map(d => h('option', {value: d}, t(d + '_dim')))))),
          profBox)
      ];
    },

    async models() {
      const [knn, rf, clusters, s] = await Promise.all([data('models', 'knn_results'), data('models', 'rf_importance'),
        data('models', 'household_clusters'), data('models', 'summary')]);
      return [
        h('div', {class: 'page-head'}, h('h1', {}, t('nav_models')), h('p', {class: 'muted'}, t('m_models'))),
        section(t('models'), t('models_cap'), table([t('model'), t('auc'), t('bal_acc'), t('recall'), t('precision')],
          knn.map((r, i) => [t('m' + i), dec(r.auc, 3), dec(r.balanced_accuracy, 3), pct(r.recall_very_vulnerable), pct(r.precision_very_vulnerable)]))),
        section(t('rf'), `AUC (test): ${dec(s.rf_auc_test, 3)}`,
          chartBox(d => Charts.bars(d, rf.filter(r => r.importance > .002).map(r => ({label: r.variable, value: r.importance, text: dec(r.importance, 3)}))))),
        section(t('clusters'), `k = ${s.kmeans_k}`,
          table([t('type'), t('households'), t('women'), t('avg_age'), t('no_work'), t('disability'), t('vv')],
            clusters.map(r => [r.cluster, int(r.households), pct(r.female), dec(r.age, 0), pct(r.no_work), pct(r.health_disability), pct(r.vv)])))
      ];
    },

    async data() {
      const [me, sources] = await Promise.all([api('/api/me', {method: 'GET'}), api('/api/sources', {method: 'GET'})]);
      const out = [h('div', {class: 'page-head'}, h('h1', {}, t('data_title')), h('p', {class: 'muted'}, t('data_lead'))),
        section(t('d_sources'), null, table([t('d_file'), t('d_size'), t('d_modified')],
          sources.map(s => [s.file, s.size ? (s.size / 1048576).toFixed(1) + ' MB' : '—', s.modified || '—']))),
        h('p', {class: 'cap'}, `${t('d_source')}: ${me.source || '—'}`)];
      if (state.role !== 'admin') { out.push(h('div', {class: 'notice'}, t('admin_only'))); return out; }
      const msg = h('div', {}), logBox = h('pre', {class: 'log', hidden: true});
      const file = h('input', {type: 'file', accept: '.csv', 'aria-label': t('d_file')});
      const upload = async ev => {
        ev.preventDefault();
        if (!file.files[0]) return;
        const fd = new FormData(); fd.append('file', file.files[0]);
        msg.replaceChildren(h('p', {class: 'cap'}, t('d_uploading')));
        const r = await fetch('/api/upload', {method: 'POST', body: fd, credentials: 'same-origin'});
        const b = await r.json();
        if (!r.ok) {
          msg.replaceChildren(h('div', {class: 'notice warn'}, t('up_' + b.error) + (b.missing ? ': ' + b.missing.join(', ') : '') + (b.expected ? ' (' + b.expected + ')' : '')));
          return;
        }
        msg.replaceChildren(h('div', {class: 'notice'}, `${t('d_saved')} ${b.saved}. ${t('d_then_rebuild')}`));
        delete state.cache['/api/sources'];
      };
      let timer;
      const poll = async () => {
        const j = await api('/api/rebuild', {method: 'GET'});
        logBox.hidden = false; logBox.textContent = j.log.join('\n');
        if (j.running) { timer = setTimeout(poll, 1500); return; }
        state.cache = {};
        msg.replaceChildren(h('div', {class: 'notice ' + (j.error ? 'warn' : '')}, j.error ? t('d_rebuild_fail') + ' ' + j.error : t('d_rebuild_ok')));
      };
      const rebuild = async () => {
        clearTimeout(timer);
        try { await api('/api/rebuild', {method: 'POST', body: '{}'}); } catch (e) { if (!(e.status === 409)) throw e; }
        msg.replaceChildren(h('p', {class: 'cap'}, t('d_rebuilding')));
        poll();
      };
      out.push(section(t('d_import'), t('d_import_lead'),
        h('form', {class: 'ctrl', onsubmit: upload}, h('label', {}, t('d_file'), file), h('button', {class: 'primary', type: 'submit'}, t('d_upload_btn'))),
        h('div', {class: 'ctrl'}, h('button', {class: 'ghost', type: 'button', onclick: rebuild}, t('d_rebuild_btn'))),
        msg, logBox));
      const log = await api('/api/audit', {method: 'GET'});
      out.push(section(t('audit'), null, table([t('at'), t('user'), t('action'), t('detail')], log.map(r => [r.at, r.username, r.action, {wrap: true, node: h('span', {}, r.detail || '')}]))));
      return out;
    }
  };

  /* ---------- boot */
  setLang(state.lang);
  state.page = (location.hash || '#home').slice(1);
  api('/api/me', {method: 'GET'}).then(me => me.user ? start(me) : showLogin()).catch(showLogin);
})();
