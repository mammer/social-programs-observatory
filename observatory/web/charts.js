/* Minimal SVG charts with no external library (works offline). All text goes through textContent. */
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const svgEl = (tag, attrs = {}, text) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const isRtl = () => document.documentElement.dir === 'rtl';

  function tooltip(host) {
    const tip = document.createElement('div'); tip.className = 'tip'; tip.hidden = true; host.appendChild(tip);
    return {
      show(ev, text) {
        const r = host.getBoundingClientRect();
        tip.textContent = text; tip.hidden = false;
        const x = Math.min(ev.clientX - r.left + 12, host.clientWidth - tip.offsetWidth);
        tip.style.left = Math.max(0, x) + 'px'; tip.style.top = Math.max(0, ev.clientY - r.top - 34) + 'px';
      },
      hide() { tip.hidden = true; }
    };
  }

  function measure(svg, texts, cls) {
    const g = svgEl('g'); svg.appendChild(g);
    let w = 0;
    texts.forEach(t => { const e = svgEl('text', cls ? {class: cls} : {}, t); g.appendChild(e); w = Math.max(w, e.getComputedTextLength()); });
    g.remove();
    return w;
  }

  /* Shorten a label with an ellipsis until it fits in `max` pixels (full text stays in the tooltip). */
  function fit(textEl, max) {
    let s = textEl.textContent;
    while (s.length > 4 && textEl.getComputedTextLength() > max) { s = s.slice(0, -2); textEl.textContent = s + '…'; }
  }

  /* Horizontal bars. rows: [{label, value, text, color?, tip?}] */
  function bars(host, rows, opts = {}) {
    host.replaceChildren();
    if (!rows.length) { host.textContent = '—'; return; }
    const W = Math.max(280, host.clientWidth || 600), bh = opts.barHeight || 22, gap = 9, R = isRtl();
    const svg = svgEl('svg', {role: 'img', 'aria-label': opts.label || '', direction: 'ltr'});
    host.appendChild(svg);
    const lw = Math.min(measure(svg, rows.map(r => r.label)) + 14, W * 0.45);
    const vw = measure(svg, rows.map(r => r.text), 'val') + 12;
    const H = rows.length * (bh + gap);
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const max = opts.max || Math.max(...rows.map(r => r.value), 1e-9);
    const scale = v => Math.max(1, (v / max) * Math.max(20, W - lw - vw));
    const tip = tooltip(host);
    rows.forEach((r, i) => {
      const y = i * (bh + gap), w = scale(r.value);
      const g = svgEl('g');
      const lab = svgEl('text', {x: R ? W - 2 : lw - 10, y: y + bh / 2 + 4, 'text-anchor': 'end'}, r.label); g.appendChild(lab); svg.appendChild(g); fit(lab, lw - 14);
      g.appendChild(svgEl('rect', {x: R ? W - lw - w : lw, y, width: w, height: bh, rx: 3, fill: r.color || 'var(--bar)'}));
      g.appendChild(svgEl('text', {class: 'val', x: R ? W - lw - w - 6 : lw + w + 6, y: y + bh / 2 + 4, 'text-anchor': R ? 'end' : 'start'}, r.text));
      g.addEventListener('pointermove', ev => tip.show(ev, r.tip || `${r.label}: ${r.text}`));
      g.addEventListener('pointerleave', () => tip.hide());
      svg.appendChild(g);
    });
  }

  /* Stacked 100% bars: rows [{label, parts:[v1,v2,v3]}], colors [c1,c2,c3] */
  function stacked(host, rows, colors, names, opts = {}) {
    host.replaceChildren();
    const W = Math.max(280, host.clientWidth || 600), bh = 18, gap = 7, R = isRtl();
    const svg = svgEl('svg', {role: 'img', 'aria-label': opts.label || '', direction: 'ltr'});
    host.appendChild(svg);
    const lw = Math.min(measure(svg, rows.map(r => r.label)) + 14, W * 0.5);
    const H = rows.length * (bh + gap);
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const span = W - lw - 6, tip = tooltip(host);
    rows.forEach((r, i) => {
      const y = i * (bh + gap), g = svgEl('g');
      const lab = svgEl('text', {x: R ? W - 2 : lw - 10, y: y + bh / 2 + 4, 'text-anchor': 'end'}, r.label); g.appendChild(lab); svg.appendChild(g); fit(lab, lw - 14);
      let acc = 0;
      r.parts.forEach((v, k) => {
        const w = v * span, x = R ? W - lw - acc - w : lw + acc;
        g.appendChild(svgEl('rect', {x, y, width: Math.max(0, w), height: bh, fill: colors[k]}));
        if (v >= 0.12) g.appendChild(svgEl('text', {class: 'val', x: x + w / 2, y: y + bh / 2 + 4, 'text-anchor': 'middle', style: k === 0 ? 'fill:#fff' : ''}, Math.round(v * 100) + '%'));
        acc += w;
      });
      g.addEventListener('pointermove', ev => tip.show(ev, `${r.label} · ` + r.parts.map((v, k) => `${names[k]} ${Math.round(v * 100)}%`).join(' · ')));
      g.addEventListener('pointerleave', () => tip.hide());
      svg.appendChild(g);
    });
  }

  /* Daily columns: rows [{date: 'YYYY-MM-DD', value}] */
  function columns(host, rows, opts = {}) {
    host.replaceChildren();
    const W = Math.max(280, host.clientWidth || 600), H = 220, m = {t: 10, b: 26, l: 46, r: 10};
    const svg = svgEl('svg', {viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': opts.label || '', direction: 'ltr'});
    host.appendChild(svg);
    const t = rows.map(r => Date.parse(r.date + 'T00:00:00Z')), t0 = Math.min(...t), t1 = Math.max(...t) + 864e5;
    const max = Math.max(...rows.map(r => r.value));
    const nice = Math.pow(10, Math.floor(Math.log10(max))) * (max / Math.pow(10, Math.floor(Math.log10(max))) > 5 ? 2 : 1);
    const top = Math.ceil(max / nice) * nice;
    const x = v => m.l + (v - t0) / (t1 - t0) * (W - m.l - m.r), y = v => H - m.b - v / top * (H - m.t - m.b);
    for (let v = 0; v <= top; v += nice) {
      svg.appendChild(svgEl('line', {x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: 'var(--line)'}));
      svg.appendChild(svgEl('text', {x: m.l - 6, y: y(v) + 4, 'text-anchor': 'end'}, v.toLocaleString('fr-FR')));
    }
    const months = new Set();
    rows.forEach(r => { const mo = r.date.slice(0, 7); if (!months.has(mo)) { months.add(mo); const d = Date.parse(mo + '-01T00:00:00Z'); if (d >= t0) svg.appendChild(svgEl('text', {x: x(d), y: H - 8}, mo.slice(5) + '/' + mo.slice(0, 4))); } });
    const bw = Math.max(1, (W - m.l - m.r) / ((t1 - t0) / 864e5) - 1), tip = tooltip(host);
    rows.forEach((r, i) => {
      const rect = svgEl('rect', {x: x(t[i]), y: y(r.value), width: bw, height: y(0) - y(r.value), fill: 'var(--accent)'});
      rect.addEventListener('pointermove', ev => tip.show(ev, `${r.date}: ${r.value.toLocaleString('fr-FR')}`));
      rect.addEventListener('pointerleave', () => tip.hide());
      svg.appendChild(rect);
    });
  }

  /* Lorenz curve: rows [{households_share, aid_share}] */
  function lorenz(host, rows, opts = {}) {
    host.replaceChildren();
    const S = Math.min(Math.max(240, host.clientWidth || 360), 380), m = 34;
    const svg = svgEl('svg', {viewBox: `0 0 ${S} ${S}`, role: 'img', 'aria-label': opts.label || '', direction: 'ltr', style: `max-width:${S}px`});
    host.appendChild(svg);
    const x = v => m + v * (S - m - 10), y = v => S - m - v * (S - m - 10);
    [0, .25, .5, .75, 1].forEach(v => {
      svg.appendChild(svgEl('line', {x1: x(0), x2: x(1), y1: y(v), y2: y(v), stroke: 'var(--line)'}));
      svg.appendChild(svgEl('text', {x: m - 6, y: y(v) + 4, 'text-anchor': 'end'}, Math.round(v * 100) + '%'));
      svg.appendChild(svgEl('text', {x: x(v), y: S - 12, 'text-anchor': 'middle'}, Math.round(v * 100) + '%'));
    });
    svg.appendChild(svgEl('line', {x1: x(0), y1: y(0), x2: x(1), y2: y(1), stroke: 'var(--muted)', 'stroke-dasharray': '4 4'}));
    const pts = rows.map(r => `${x(r.households_share)},${y(r.aid_share)}`).join(' ');
    svg.appendChild(svgEl('polyline', {points: pts, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2.5}));
  }

  /* Scatter with labels: rows [{x, y, label, size?, color?, tip?}] */
  function scatter(host, rows, opts = {}) {
    host.replaceChildren();
    const W = Math.max(280, host.clientWidth || 600), H = Math.min(Math.max(280, W * .55), 440), m = 30;
    const svg = svgEl('svg', {viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': opts.label || '', direction: 'ltr'});
    host.appendChild(svg);
    const xs = rows.map(r => r.x), ys = rows.map(r => r.y);
    const x0 = Math.min(...xs, 0) - .6, x1 = Math.max(...xs, 0) + .6, y0 = Math.min(...ys, 0) - .5, y1 = Math.max(...ys, 0) + .5;
    const x = v => m + (v - x0) / (x1 - x0) * (W - 2 * m), y = v => H - m - (v - y0) / (y1 - y0) * (H - 2 * m);
    svg.appendChild(svgEl('line', {x1: x(0), x2: x(0), y1: m, y2: H - m, stroke: 'var(--line)'}));
    svg.appendChild(svgEl('line', {x1: m, x2: W - m, y1: y(0), y2: y(0), stroke: 'var(--line)'}));
    const tip = tooltip(host), placed = [];
    rows.forEach(r => {
      const g = svgEl('g'), rad = r.size || 6;
      g.appendChild(svgEl('circle', {cx: x(r.x), cy: y(r.y), r: rad, fill: r.color || 'var(--accent)', 'fill-opacity': .75}));
      const t = svgEl('text', {class: 'val', x: x(r.x), y: y(r.y) - rad - 4, 'text-anchor': 'middle'}, r.label);
      g.appendChild(t); svg.appendChild(g);
      const b = t.getBBox();
      if (placed.some(p => !(b.x > p.x + p.width || b.x + b.width < p.x || b.y > p.y + p.height || b.y + b.height < p.y))) t.remove(); else placed.push(b);
      g.addEventListener('pointermove', ev => tip.show(ev, r.tip || r.label));
      g.addEventListener('pointerleave', () => tip.hide());
    });
  }

  window.Charts = {bars, stacked, columns, lorenz, scatter};
})();
