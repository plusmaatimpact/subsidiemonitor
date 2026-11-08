/* Plusmaat Subsidiemonitor — kleine runtime voor de dashboards.
 * Laadt de JSON-bestanden uit /data, rekent de berekeningen (dash.calc) uit
 * en tekent alle elementen met data-draw opnieuw zodra data, filters of
 * schermbreedte veranderen.
 *
 * Een pagina zet vóór dit script:
 *   window.DASH_SOURCES = { naam: 'data/bestand.json' | {url, filter} }
 *   window.DASH_PARAMS  = { filter: standaardwaarde }
 */
(function () {
  'use strict';
  const SOURCES = window.DASH_SOURCES || {};
  const state = {};
  const calcs = {};
  const cache = {};
  const draws = [];
  const onDatas = [];
  let params = Object.assign({}, window.DASH_PARAMS || {});
  const defaults = Object.assign({}, params);

  Object.keys(SOURCES).forEach((id) => { state[id] = {status: 'loading', data: []}; });

  function calcResult(id) {
    if (cache[id]) return cache[id];
    const c = calcs[id];
    const ins = c.inputs.map((i) => dash.data(i));
    if (ins.some((x) => x.status === 'error')) return {status: 'error', data: []};
    if (ins.some((x) => x.status !== 'ok')) return {status: 'loading', data: []};
    try {
      const d = c.fn(...ins.map((x) => x.data));
      return (cache[id] = {status: 'ok', data: d});
    } catch (e) {
      console.error('Berekening ' + id + ' mislukt', e);
      return (cache[id] = {status: 'error', data: [], message: String(e)});
    }
  }

  let pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; run(); });
  }

  function run() {
    onDatas.forEach((fn) => { try { fn(); } catch (e) { console.error(e); } });
    draws.forEach(([name, fn]) => {
      document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => {
        if (el.closest('[hidden]')) return;
        try { fn(el); } catch (e) { console.error('Tekenen ' + name + ' mislukt', e); }
      });
    });
    document.querySelectorAll('[data-source]').forEach((el) => {
      const ids = el.getAttribute('data-source').split(/\s+/);
      const st = ids.map((i) => dash.data(i).status);
      const s = st.includes('error') ? 'error' : st.includes('loading') ? 'loading' : null;
      if (s) el.setAttribute('data-dash-source-state', s); else el.removeAttribute('data-dash-source-state');
    });
  }

  const dash = {
    colors: ['#14B8A6', '#5577A3', '#F59E0B', '#0B2545', '#7DD3C0', '#94A3B8', '#0F766E', '#C2410C', '#8B5CF6', '#64748B'],
    data(id) {
      if (calcs[id]) return calcResult(id);
      return state[id] || {status: 'missing', data: []};
    },
    calc(id, def) { calcs[id] = def; },
    loader() {},
    draw(name, fn) {
      if (typeof fn === 'function') { draws.push([name, fn]); return; }
      // dash.draw('naam') zonder functie: teken dat onderdeel nu opnieuw (na sorteren, zoeken, wissen)
      draws.filter(([n]) => n === name).forEach(([, f]) => {
        document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => {
          if (el.closest('[hidden]')) return;
          try { f(el); } catch (e) { console.error('Tekenen ' + name + ' mislukt', e); }
        });
      });
    },
    onData(fn) { onDatas.push(fn); },
    params() { return Object.assign({}, params); },
    setParams(p) {
      Object.keys(p).forEach((k) => { if (p[k] == null) delete params[k]; else params[k] = p[k]; });
      schedule();
    },
    resetParams() { params = Object.assign({}, defaults); schedule(); },
    setLink(name) { try { history.replaceState(null, '', '#' + name); } catch (e) { /* niets */ } },
    refresh() {}
  };
  window.dash = dash;

  const loads = Object.entries(SOURCES).map(async ([id, src]) => {
    const spec = typeof src === 'string' ? {url: src} : src;
    try {
      const r = await fetch(spec.url, {cache: 'no-cache'});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      let d = await r.json();
      if (spec.filter) d = d.filter(spec.filter);
      state[id] = {status: 'ok', data: d};
    } catch (e) {
      console.error('Laden ' + id + ' mislukt', e);
      state[id] = {status: 'error', data: [], message: String(e)};
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    run();
    Promise.all(loads).then(() => { Object.keys(cache).forEach((k) => delete cache[k]); run(); });
    new MutationObserver((recs) => {
      if (recs.some((r) => (r.oldValue === null) === r.target.hasAttribute('hidden'))) schedule();
    }).observe(document.body, {attributes: true, subtree: true, attributeFilter: ['hidden'], attributeOldValue: true});
    let w = window.innerWidth;
    window.addEventListener('resize', () => { if (window.innerWidth !== w) { w = window.innerWidth; schedule(); } });
  });
})();
