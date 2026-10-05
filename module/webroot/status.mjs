const NR = [-125, -115, -105, -95];
const WIFI = [-88, -77, -66, -55];
const same = (a, b) => Array.isArray(a) && a.length === b.length && a.every((v, i) => v === b[i]);
const number = (value, low, high) => {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isInteger(n) && n >= low && n <= high ? n : null;
};
function array(value, low, high) {
  try {
    const result = JSON.parse(value);
    return Array.isArray(result) && result.length === 4 && result.every((n, i) =>
      number(n, low, high) !== null && (!i || n > result[i - 1])) ? result : null;
  } catch { return null; }
}
export function signalLevel(value, thresholds) {
  if (number(value, -140, 0) === null || !Array.isArray(thresholds)) return null;
  return thresholds.filter(t => value >= t).length;
}
export function parseStatus(text) {
  const sections = {};
  let section = '';
  for (const line of text.replaceAll('\r', '').split('\n')) {
    if (line.startsWith('@@')) { section = line.slice(2); sections[section] = []; }
    else if (section) sections[section].push(line.trim());
  }
  const lines = key => sections[key] || [];
  const meta = Object.fromEntries(lines('meta').map(l => {
    const i = l.indexOf('='); return [l.slice(0, i), l.slice(i + 1)];
  }).filter(([k]) => k));
  const errors = Object.keys(sections).filter(k => sections[k].includes('__QUERY_FAILED__'));
  // A timed-out command may have printed a prefix: never treat that prefix as fresh data.
  for (const key of errors) sections[key] = [];
  let defaults = null, phone = null;
  const phones = [];
  for (const line of lines('carrier')) {
    if (line.startsWith('mNoSimConfig')) break;
    const id = line.match(/^Phone Id = (\d+)/);
    if (id) { phone = { id: Number(id[1]), thresholds: defaults, primary: null, rsrp: null, level: null }; phones.push(phone); }
    const match = line.match(/^5g_nr_ssrsrp_thresholds_int_array = (.+)$/);
    if (match) {
      const value = array(match[1], -140, -44);
      if (phone) phone.thresholds = value; else defaults = value;
    }
  }
  phone = null;
  for (const line of lines('telephony')) {
    const id = line.match(/^Phone Id=(\d+)/);
    if (id) {
      phone = phones.find(p => p.id === Number(id[1]));
      if (!phone) { phone = { id: Number(id[1]), thresholds: null, rsrp: null, level: null }; phones.push(phone); }
    }
    if (!phone || !line.startsWith('mSignalStrength=')) continue;
    phone.primary = line.match(/primary=CellSignalStrength(\w+)/)?.[1] || null;
    const nr = line.match(/mNr=CellSignalStrengthNr:\{([^}]+)\}/)?.[1] || '';
    phone.rsrp = number(nr.match(/ssRsrp\s*=\s*(-?\d+)/)?.[1], -140, -44);
    phone.level = number(nr.match(/\blevel\s*=\s*(\d+)/)?.[1], 0, 4);
    const lte = line.match(/mLte=CellSignalStrengthLte:([^,}]+)/)?.[1] || '';
    phone.lteRsrp = number(lte.match(/\brsrp\s*=\s*(-?\d+)/)?.[1], -140, -44);
    phone.lteLevel = number(lte.match(/\blevel\s*=\s*(\d+)/)?.[1], 0, 4);
  }
  const wifiText = lines('wifi').join('\n');
  const state = wifiText.match(/Supplicant state:\s*([A-Z_]+)/)?.[1];
  const connected = state ? state === 'COMPLETED' : null;
  const thresholds = array(JSON.stringify(lines('wifi_thresholds').filter(l => /^-?\d+$/.test(l)).map(Number)), -127, 0);
  const levels = lines('wifi_ui').map(l => l.match(/\|level\|(\*\*)?(null|\d+)$/)).filter(Boolean);
  const rawLevel = levels.length ? number(levels.at(-1)[2], 0, 4) : null;
  const level = connected === true ? rawLevel : null;
  const activePhones = phones.filter(p => p.rsrp !== null || p.lteRsrp !== null);
  const requiredPhones = activePhones.length ? activePhones : phones.slice(0, 1);
  return {
    meta, phones, errors,
    carrierVisible: meta.carrier_visible === 'true' ? true : meta.carrier_visible === 'false' ? false : null,
    overlays: Object.fromEntries(['carrier', 'wifi'].map(kind => {
      const line = lines('overlays').find(l => l.endsWith(`signalbars.${kind}`));
      return [kind, line ? line.startsWith('[x]') : null];
    })),
    nrEffective: requiredPhones.length && requiredPhones.every(p => p.thresholds) ? requiredPhones.every(p => same(p.thresholds, NR)) : null,
    wifiEffective: thresholds ? same(thresholds, WIFI) : null,
    wifi: { thresholds, connected, level, visibleBars: level === null ? null : [0,1,2,2,3][level],
      rssi: connected === true ? number(wifiText.match(/RSSI:\s*(-?\d+)/)?.[1], -126, 0) : null },
  };
}
