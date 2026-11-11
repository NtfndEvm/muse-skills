#!/usr/bin/env node
// bench.js — environment check before a mint. Read-only unless --live is given.
//   node bench.js            rank RPCs, WS head latency, clock offset, baw status/preview latency (harmless balanceOf preview)
//   node bench.js --ca       (re)build ~/.config/certs/system-ca.pem from the macOS keychain (fixes Node TLS errors)
//   node bench.js --live     ALSO execute one harmless 0-value tx (USDT balanceOf, ~0.00002 BNB gas) to measure
//                            execute + inclusion latency. Costs real gas: only with the user's explicit OK.
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync } = require('child_process');

if (process.argv.includes('--ca')) {
  const pem = process.env.FASTMINT_CA || path.join(os.homedir(), '.config', 'certs', 'system-ca.pem');
  fs.mkdirSync(path.dirname(pem), { recursive: true });
  let out = '';
  for (const kc of ['/Library/Keychains/System.keychain', path.join(os.homedir(), 'Library/Keychains/login.keychain-db'), '/System/Library/Keychains/SystemRootCertificates.keychain']) {
    const r = spawnSync('security', ['find-certificate', '-a', '-p', kc], { encoding: 'utf8', maxBuffer: 64 << 20 });
    if (r.stdout) out += r.stdout;
  }
  fs.writeFileSync(pem, out);
  console.log(`wrote ${pem}: ${(out.match(/BEGIN CERT/g) || []).length} certs. lib.js auto-loads it.`);
  process.exit(0);
}

const L = require('./lib');
const { ethers } = L;
const USDT = '0x55d398326f99059fF775485246999027B3197955';
const live = process.argv.includes('--live');

(async () => {
  const clk = await L.syncClock();
  console.log(`clock offset ${clk.offsetMs >= 0 ? '+' : ''}${clk.offsetMs}ms (${clk.source})  node ${process.version}  CA ${process.env.NODE_EXTRA_CA_CERTS || 'default'}`);

  console.log('\n== RPC (2 rounds, best ms, block lag) ==');
  const w = await L.warmRpcs({ rounds: 2 });
  for (const r of w) console.log(`${r.err ? 'ERR ' + r.err : String(r.ms).padStart(5) + 'ms' + (r.lag ? ' lag' + r.lag : '     ')}`.padEnd(28) + L.hostOf(r.u));
  for (const u of L.fastRpcs(3)) { try { await L.rpcOne(u, 'eth_call', [{ to: USDT, data: '0x18160ddd' }, 'pending'], 3000); console.log('pending-tag OK ', L.hostOf(u)); } catch (e) { console.log('pending-tag ERR', L.hostOf(u), (e.message || '').slice(0, 50)); } }

  console.log('\n== WS newHeads (receive delay vs block ts, 3 heads each) ==');
  await new Promise(res => {
    const seen = {}; const stop = L.wsHeads(h => { seen[h.url] = (seen[h.url] || 0) + 1; if (seen[h.url] <= 3) console.log(`${L.hostOf(h.url)} #${h.number} ts ${h.ts} delay ${((h.recvMs / 1000) - h.ts).toFixed(2)}s`); });
    setTimeout(() => { stop(); res(); }, 4000);
  });

  console.log('\n== baw ==');
  let t = Date.now(); const st = await L.bawStatus(); console.log(`wallet status ${st} (${Date.now() - t}ms)`);
  if (st !== 'CONNECTED') { console.log('not connected — stop here; the user must sign in (never run auth signin automatically).'); process.exit(1); }
  const addr = await L.bawEvmAddress();
  const settings = await L.baw(['wallet', 'settings']);
  const d = settings.json && settings.json.data || {};
  console.log(`from ${addr} | devMode ${d.devMode && d.devMode.enabled ? 'ON until ' + d.devMode.expiresAt : 'OFF'} | session until ${d.sessionExpireTime} | devMode quota used ${d.developerModeQuotaUsed}/${d.devMode && d.devMode.dailyLimit} USD`);
  const bal = BigInt(await L.rpc('eth_getBalance', [addr, 'latest'])); console.log(`BNB ${ethers.formatEther(bal)}`);
  const agent = await L.agentIdOf(addr).catch(() => null); console.log(`agentId ${agent && agent.handle ? agent.handle + '.ai tokenId=' + agent.tokenId : 'NONE'}`);
  const data = '0x70a08231' + addr.slice(2).toLowerCase().padStart(64, '0');
  const times = [];
  let req = null;
  for (let i = 0; i < 3; i++) {
    const r = await L.baw(['contract-call', 'preview', '--binanceChainId', '56', '--from', addr, '--to', USDT, '--value', '0', '--inputData', data], 30000);
    const ok = r.ok && r.json.data && r.json.data.simulationResult && r.json.data.simulationResult.simulationCode === '000000000';
    times.push(r.ms); if (ok) req = r.json.data.requestId;
    console.log(`preview #${i + 1} ${r.ms}ms ${ok ? 'OK' : 'FAIL ' + L.safeJson(r.json && r.json.error).slice(0, 200)}`);
  }
  const pv = Math.min(...times);
  console.log(`\nestimate: head-detect ≈0.5s + preview ${(pv / 1000).toFixed(2)}s + execute ≈0.7s + inclusion ≈0.5s → broadcast ≈T+${((500 + pv + 700) / 1000).toFixed(1)}s, included ≈T+${((500 + pv + 1200) / 1000).toFixed(1)}s (execute measured 707ms on 2026-11-11)`);

  if (live && req) {
    console.log('\n== LIVE execute test (harmless USDT balanceOf, 0 value) ==');
    const t0 = L.now();
    const ex = await L.baw(['contract-call', 'execute', '--requestId', req], 90000);
    const ed = ex.json && ex.json.data;
    console.log(`execute ${ex.ms}ms → ${ed ? ed.status + ' ' + (ed.txHash || '') : 'ERR ' + L.safeJson(ex.json || ex.stdout).slice(0, 300)}`);
    if (ed && ed.txHash) {
      let rc = null; const until = Date.now() + 90000;
      while (!rc && Date.now() < until) { try { rc = await L.rpc('eth_getTransactionReceipt', [ed.txHash], { urls: L.fastRpcs(4), timeoutMs: 2500 }); } catch {} if (!rc) await L.sleep(200); }
      if (rc) { const b = await L.rpc('eth_getBlockByNumber', [rc.blockNumber, false]); console.log(`included block ${parseInt(rc.blockNumber, 16)} status ${parseInt(rc.status, 16)} gasUsed ${parseInt(rc.gasUsed, 16)} | execute→receipt ${((L.now() - t0 - ex.ms) / 1000).toFixed(2)}s | block ts − execute-sent = ${(parseInt(b.timestamp, 16) - t0 / 1000).toFixed(2)}s | ${L.SCAN}/tx/${ed.txHash}`); }
      else console.log('no receipt in 90s — check ' + L.SCAN + '/tx/' + ed.txHash);
    }
  } else if (live) console.log('\n--live: no OK preview to execute');
  process.exit(0);
})().catch(e => { console.error('bench ERR', e.stack || e.message); process.exit(1); });
