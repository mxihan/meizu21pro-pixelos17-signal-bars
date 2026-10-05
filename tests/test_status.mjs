import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const source = new URL('../module/webroot/status.mjs', import.meta.url);
const api = existsSync(source) ? await import(source.href) : {};
const fixture = readFileSync(new URL('./fixtures/status.txt', import.meta.url), 'utf8');

test('per-phone NR config takes precedence over global defaults', () => {
  assert.equal(typeof api.parseStatus, 'function', 'status parser not implemented');
  const status = api.parseStatus(fixture);
  assert.deepEqual(status.phones[0].thresholds, [-125,-115,-105,-95]);
  assert.deepEqual(status.phones[1].thresholds, [-110,-90,-80,-65]);
  assert.equal(status.phones[0].rsrp, -110);
  assert.equal(status.phones[0].level, 2);
});

test('later runtime carrier overrides take precedence over resource config', () => {
  assert.equal(typeof api.parseStatus, 'function');
  const status = api.parseStatus(fixture.replace('mOverrideConfigs : null',
    'mOverrideConfigs :\n  5g_nr_ssrsrp_thresholds_int_array = [-120, -110, -100, -90]'));
  assert.deepEqual(status.phones[0].thresholds, [-120,-110,-100,-90]);
});

test('Wi-Fi uses latest SystemUI level and preserves RSSI', () => {
  assert.equal(typeof api.parseStatus, 'function');
  const status = api.parseStatus(fixture);
  assert.equal(status.wifi.rssi, -72);
  assert.equal(status.wifi.level, 2);
  assert.equal(status.wifi.visibleBars, 2);
  assert.equal(status.wifi.connected, true);
});

test('invalid NR sentinel and disconnected Wi-Fi remain unavailable', () => {
  assert.equal(typeof api.parseStatus, 'function');
  const status = api.parseStatus(fixture.replace('COMPLETED', 'DISCONNECTED'));
  assert.equal(status.phones[1].rsrp, null);
  assert.equal(status.wifi.rssi, null);
  assert.equal(status.wifi.level, null);
});

test('command failures and missing process are unknown, never healthy', () => {
  assert.equal(typeof api.parseStatus, 'function');
  const status = api.parseStatus('@@meta\ncarrier_visible=unknown\n@@wifi_thresholds\n__QUERY_FAILED__\n@@carrier\n__QUERY_FAILED__');
  assert.equal(status.wifi.thresholds, null);
  assert.equal(status.carrierVisible, null);
  assert.equal(status.nrEffective, null);
  assert.equal(status.wifiEffective, null);
  assert.ok(status.errors.includes('carrier'));
});

test('threshold boundaries yield the correct level without counting invalid RSSI', () => {
  assert.equal(typeof api.signalLevel, 'function');
  for (const [value, level] of [[-126,0],[-125,1],[-115,2],[-105,3],[-95,4],[-70,4],[2147483647,null],[null,null]]) {
    assert.equal(api.signalLevel(value, [-125,-115,-105,-95]), level);
  }
  assert.equal(api.signalLevel(-70, null), null);
});
