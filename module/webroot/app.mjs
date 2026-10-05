import { exec } from './vendor/kernelsu.js';
import { parseStatus, signalLevel } from './status.mjs';

const byId = id => document.getElementById(id);
const text = (tag, value, className) => {
  const node = document.createElement(tag); node.textContent = value;
  if (className) node.className = className;
  return node;
};
const known = value => value === true ? '已生效' : value === false ? '未生效' : '未知';
const thresholds = values => values ? `${values.join(' / ')} dBm` : '未读到';
function rows(target, pairs) {
  target.replaceChildren(...pairs.map(([label, value]) => {
    const row = document.createElement('div'); row.append(text('dt', label), text('dd', value)); return row;
  }));
}
function bars(target, level, count) {
  target.replaceChildren(...Array.from({length: count}, (_, i) => {
    const bar = document.createElement('i'); bar.style.height = `${10 + i * 5}px`;
    if (level !== null && i < level) bar.className = 'on'; return bar;
  }));
  target.setAttribute('aria-label', level === null ? '等级未知' : `${level} / ${count} 格`);
}
function values(target, entries) {
  target.replaceChildren(...entries.map(([value, unit, label]) => {
    const cell = document.createElement('div'), main = text('div', value === null ? '—' : value, 'value');
    main.append(text('small', ` ${unit}`)); cell.append(main, text('div', label, 'label')); return cell;
  }));
}
function render(status) {
  const { meta, wifi } = status;
  byId('version').textContent = meta.version || '版本未知';
  const issues = [];
  if (meta.disabled === '1') issues.push('模块已标记禁用，重启后应用。');
  if (meta.baseline !== 'ok') issues.push('ROM 基准不匹配或无法核对。');
  if (meta.compatibility_error === '1') issues.push('启动时兼容性检查未通过。');
  if (status.carrierVisible === false) issues.push('CarrierConfig 读不到覆盖 APK，请关闭该应用的“卸载模块”并重启。');
  if (status.errors.length) issues.push('部分状态查询失败，相关值暂不可用。');
  if (status.nrEffective === false) issues.push('当前卡的 NR 生效阈值与本模块不同。');
  if (status.wifiEffective === false) issues.push('Wi-Fi 生效阈值与本模块不同。');
  if (status.overlays.carrier === false || status.overlays.wifi === false) issues.push('资源覆盖尚未启用。');
  if (meta.nr_disabled === '1' || meta.wifi_disabled === '1') issues.push('组件禁用标记将在下次重启应用。');
  const healthy = !issues.length && status.nrEffective === true && status.wifiEffective === true && status.carrierVisible === true && status.overlays.carrier === true && status.overlays.wifi === true;
  byId('health').textContent = healthy ? '运行正常' : issues.length ? '需要检查' : '状态不完整';
  byId('health').className = healthy ? 'pill' : 'pill warn';
  byId('error').hidden = !issues.length;
  byId('error').textContent = issues.join(' ');
  rows(byId('module'), [
    ['设备', `${meta.device || '未知'} · SDK ${meta.sdk || '未知'}`],
    ['ROM 基准', meta.baseline === 'ok' ? '匹配' : '未匹配'],
    ['NR 覆盖', known(status.overlays.carrier)], ['Wi-Fi 覆盖', known(status.overlays.wifi)],
    ['CarrierConfig 挂载', status.carrierVisible === true ? 'APK 可读取' : status.carrierVisible === false ? 'APK 不可读取' : '进程未运行 / 未知'],
  ]);
  bars(byId('wifi-bars'), wifi.visibleBars, 3);
  values(byId('wifi-values'), [[wifi.rssi, 'dBm', 'RSSI'], [wifi.level, '/ 4', '系统内部等级']]);
  rows(byId('wifi-config'), [['连接', wifi.connected === true ? '已连接' : wifi.connected === false ? '未连接' : '未知'],
    ['生效门槛', thresholds(wifi.thresholds)], ['门槛推算等级', signalLevel(wifi.rssi, wifi.thresholds) ?? '—']]);
  byId('phones').replaceChildren(...status.phones.map(phone => {
    const card = text('article', '', 'card'), head = text('div', '', 'card-head');
    const signalBars = text('div', '', 'bars');
    const level = phone.primary === 'Nr' && phone.rsrp !== null ? phone.level : phone.primary === 'Lte' && phone.lteRsrp !== null ? phone.lteLevel : null;
    head.append(text('h2', `卡槽 ${phone.id + 1} · ${phone.primary === 'Nr' ? 'NR' : phone.primary === 'Lte' ? 'LTE' : phone.primary || '未知'}`), signalBars);
    bars(signalBars, level, 4);
    const metrics = text('div', '', 'values');
    values(metrics, [[phone.primary === 'Lte' ? phone.lteRsrp : phone.rsrp, 'dBm', phone.primary === 'Lte' ? 'LTE RSRP' : 'NR SS-RSRP'], [level, '/ 4', '系统实际等级']]);
    const config = document.createElement('dl');
    rows(config, [['NR 生效门槛', thresholds(phone.thresholds)], ['NR 门槛推算等级', signalLevel(phone.rsrp, phone.thresholds) ?? '—']]);
    card.append(head, metrics, config, text('p', phone.primary === 'Nr' ? '当前主信号为 NR，图标使用 NR 等级。' : '当前主信号未采用 NR；5G 标签与信号格可由不同网络决定。', 'hint'));
    return card;
  }));
}
let pending = false, timer;
async function refresh() {
  clearTimeout(timer);
  if (pending || document.hidden) return;
  pending = true; byId('refresh').disabled = true;
  try {
    if (!globalThis.ksu || typeof globalThis.ksu.exec !== 'function') throw new Error('请从 KernelSU 的模块 WebUI 打开此页。');
    let deadline;
    let result;
    try {
      result = await Promise.race([
        exec('sh /data/adb/modules/meizu21pro_signal_bars/status.sh'),
        new Promise((_, reject) => { deadline = setTimeout(() => reject(new Error('状态读取超时，可稍后重试。')), 60000); }),
      ]);
    } finally { clearTimeout(deadline); }
    if (result.errno !== 0) throw new Error('读取失败，请检查模块与 WebUI 的 root 执行权限。');
    if (!result.stdout.includes('@@meta')) throw new Error('未收到有效状态数据。');
    render(parseStatus(result.stdout)); byId('snapshot').classList.remove('stale');
    byId('updated').textContent = `更新于 ${new Date().toLocaleTimeString('zh-CN', {hour12: false})}`;
  } catch (error) {
    byId('error').hidden = false; byId('error').textContent = error.message;
    byId('snapshot').classList.add('stale'); byId('updated').textContent = '刷新失败 · 显示内容可能已过时';
  } finally {
    pending = false; byId('refresh').disabled = false;
    if (!document.hidden && globalThis.ksu) timer = setTimeout(refresh, 10000);
  }
}
byId('refresh').addEventListener('click', refresh);
document.addEventListener('visibilitychange', () => { clearTimeout(timer); if (!document.hidden) refresh(); });
refresh();
