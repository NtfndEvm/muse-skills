#!/usr/bin/env node
// fire.js — FCFS one-shot contract call through Binance Agentic Wallet (baw) on BSC, tuned for < 5s.
//
// Timeline it aims for (measured on this machine: preview ≈ 0.7s, execute ≈ 1–2s, BSC block ≈ 0.5s):
//   T-3s   spin eth_call (latest+pending) on the 4 fastest RPCs every 100ms; WS newHeads + HTTP head poll
//   T+0    clock trigger: first preview goes out at the (NTP-corrected) start time, no waiting for a block
//   T+0.4  head trigger: a sealed block with ts >= start → preview (if the clock one is still in flight, a 2nd)
//   T+x    eth_call OK trigger: a node simulates success → preview
//   first preview with simulationCode 000000000 → execute ONCE → receipt
// Safety: never runs auth signin, never broadcasts twice (lock file), --dry stops before execute,
// value > maxValue refused, preview RISK / allowance / authority changes refused.
'use strict';
const L = require('./lib');
const { ethers, log } = L;
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const HELP = `usage: node fire.js --to 0xC (--data 0x... | --sig "fn(type,..)" --args '[..]') [--start <t>] [options]
  --value <BNB>        BNB to send (decimal, default 0). Paid mint needs an explicit amount.
  --maxValue <BNB>     safety cap; required when --value > 0; refuses if value > cap
  --start <t>          unix seconds | HH:MM[:SS] ${L.TZ_LABEL} | ISO-8601 (omit = fire now)
  --args '[..]'        JSON array. Dynamic entries allowed: "$wallet", "$agentId", "$now+1800",
                       {"getter":"totalMinted()","add":1}, {"getter":"saleStart()","at":"0x.."}
                       Dynamic args are re-read right before every preview.
  --lead <ms>          start spinning this long before start (default 3000)
  --interval <ms>      eth_call spin interval (default 100)
  --clockFire <ms>     send a preview at start+ms by clock, before any block/eth_call confirms (default 0; -1 off)
  --burst <ms>         clock+head triggers keep previewing this long after start (default 3000); after that only eth_call OK does
  --gap <ms>           min spacing between previews (default 350)      --inflight <n>  max concurrent previews (default 3)
  --maxPreviews <n>    give up after this many previews (default 40)
  --timeout <s>        keep retrying 'not started' this long after start (default 600)
  --grace <s>          treat Unknown reverts / sim failures as 'wait' until start+grace (default 10)
  --once               single preview, single execute, no retries
  --dry                everything incl. preview, stop before execute     --noPreview  with --dry: stop before preview
  --noEager            do not trigger on head ts >= start                --noWs       no WebSocket heads
  --gasLimit <n>       pass to preview (cap, only if the user asked)
  --expectNft <n>      execute only if the preview shows exactly n NFTs (Erc721/Erc1155 from --to) arriving in the wallet
  --gateSim            rehearsal aid: ignore eth_call OK before --start (mimics a NotStarted gate on an always-OK call)
  --from 0x..          wallet (default: baw wallet address on chain 56)
  --abi 0x..           extra address whose Sourcify ABI is used for error decoding (default --to)
  --waitOn <regex>     extra revert names to keep retrying;  --fatalOn <regex> extra names to stop on
  --label <name>       run label for log/lock files`;

const a = process.argv.slice(2);
const o = { value: '0', lead: 3000, interval: 100, clockFire: 0, burst: 3000, gap: 350, inflight: 3, maxPreviews: 40, timeout: 600, grace: 10 };
for (let i = 0; i < a.length; i++) {
  const k = a[i]; const nx = () => a[++i];
  switch (k) {
    case '--to': o.to = nx(); break; case '--data': o.data = nx(); break; case '--sig': o.sig = nx(); break;
    case '--args': o.args = nx(); break; case '--value': o.value = nx(); break; case '--maxValue': o.maxValue = nx(); break;
    case '--start': o.start = nx(); break; case '--lead': o.lead = +nx(); break; case '--interval': o.interval = +nx(); break;
    case '--clockFire': o.clockFire = +nx(); break; case '--burst': o.burst = +nx(); break; case '--gap': o.gap = +nx(); break; case '--inflight': o.inflight = +nx(); break;
    case '--maxPreviews': o.maxPreviews = +nx(); break; case '--timeout': o.timeout = +nx(); break; case '--grace': o.grace = +nx(); break;
    case '--once': o.once = true; break; case '--dry': o.dry = true; break; case '--noPreview': o.noPreview = true; break;
    case '--noEager': o.noEager = true; break; case '--noWs': o.noWs = true; break; case '--gasLimit': o.gasLimit = +nx(); break;
    case '--expectNft': o.expectNft = +nx(); break; case '--gateSim': o.gateSim = true; break;
    case '--from': o.from = nx(); break; case '--abi': o.abi = nx(); break; case '--label': o.label = nx(); break;
    case '--waitOn': o.waitOn = new RegExp(nx(), 'i'); break; case '--fatalOn': o.fatalOn = new RegExp(nx(), 'i'); break;
    case '-h': case '--help': console.log(HELP); process.exit(0);
    default: console.error('unknown arg ' + k + '\n' + HELP); process.exit(2);
  }
}
const die = (m, code = 1) => { log('STOP ' + m); printTimeline(); process.exit(code); };
if (!o.to || !ethers.isAddress(o.to)) die('--to missing/invalid', 2);
o.to = ethers.getAddress(o.to);

// ---- calldata (static or dynamic) ----
let fnFrag = null, iface = null, rawArgs = null, dynamic = false;
if (o.sig) {
  fnFrag = ethers.FunctionFragment.from(o.sig.startsWith('function') ? o.sig : 'function ' + o.sig);
  iface = new ethers.Interface([fnFrag]);
  rawArgs = o.args ? JSON.parse(o.args) : [];
  if (rawArgs.length !== fnFrag.inputs.length) die(`--args has ${rawArgs.length} values, ${fnFrag.name} takes ${fnFrag.inputs.length}`, 2);
  dynamic = rawArgs.some(isDyn);
  if (!dynamic) { try { o.data = iface.encodeFunctionData(fnFrag, rawArgs); } catch (e) { die('cannot encode --args for ' + o.sig + ': ' + e.message, 2); } }
}
function isDyn(v) { return (typeof v === 'string' && v.startsWith('$')) || (v && typeof v === 'object' && !Array.isArray(v) && v.getter); }
const getterIfaces = new Map();
async function resolveArg(v, ctx) {
  if (typeof v === 'string' && v.startsWith('$')) {
    if (v === '$wallet') return ctx.wallet;
    if (v === '$agentId') { if (ctx.agentId == null) throw new Error('$agentId: wallet has no Agent ID'); return ctx.agentId; }
    if (v === '$zero') return ethers.ZeroAddress;
    const m = v.match(/^\$now([+-]\d+)?$/); if (m) return BigInt(Math.floor(L.now() / 1000) + (+(m[1] || 0)));
    throw new Error('unknown dynamic arg ' + v);
  }
  if (v && typeof v === 'object' && v.getter) {
    const sig = v.getter.includes('(') ? v.getter : v.getter + '()';
    const key = sig + '@' + (v.at || o.to);
    let gi = getterIfaces.get(key);
    if (!gi) { gi = new ethers.Interface([`function ${sig} view returns (uint256)`]); getterIfaces.set(key, gi); }
    const fname = sig.replace(/\(.*$/, '');
    const gargs = (v.args || []).map(x => typeof x === 'string' && x.startsWith('$') ? (x === '$wallet' ? ctx.wallet : x === '$agentId' ? ctx.agentId : x) : x);
    const r = await L.rpc('eth_call', [{ to: ethers.getAddress(v.at || o.to), data: gi.encodeFunctionData(fname, gargs) }, v.block || 'pending'], { urls: L.fastRpcs(4), timeoutMs: 1500 });
    let out = BigInt(r);
    if (v.add != null) out += BigInt(v.add);
    if (v.mul != null) out *= BigInt(v.mul);
    return out;
  }
  return v;
}
async function buildData(ctx) {
  if (!dynamic) return o.data;
  const vals = [];
  for (const v of rawArgs) vals.push(await resolveArg(v, ctx));
  return iface.encodeFunctionData(fnFrag, vals);
}
if (!dynamic && (!o.data || !/^0x([0-9a-fA-F]{2})*$/.test(o.data) || o.data.length < 10)) die('--data (or --sig) missing/invalid hex', 2);

// ---- value ----
let valueWei, maxWei;
try { valueWei = ethers.parseEther(String(o.value)); } catch { die('bad --value (BNB decimal, e.g. 0.005)', 2); }
if (valueWei > 0n) {
  if (o.maxValue == null) die('--value > 0 requires --maxValue (explicit cap the user approved)', 2);
  maxWei = ethers.parseEther(String(o.maxValue));
  if (valueWei > maxWei) die(`value ${o.value} BNB > maxValue ${o.maxValue} BNB — refusing`, 2);
} else maxWei = o.maxValue != null ? ethers.parseEther(String(o.maxValue)) : 0n;

// ---- files ----
const selector = (o.sig ? fnFrag.selector : o.data.slice(0, 10)).toLowerCase();
const label = o.label || `${o.to.slice(0, 8)}_${selector}`;
const RUNS = path.join(__dirname, 'runs'); fs.mkdirSync(RUNS, { recursive: true });
const stamp = new Date(Date.now() + 7 * 3600e3).toISOString().slice(0, 19).replace(/[-:T]/g, '');
L.setLogFile(path.join(RUNS, `${stamp}_${label}${o.dry ? '_dry' : ''}.log`));
// lock key: exact calldata when static; to|selector|value when args are dynamic (same mint, different nonce-ish args)
const lockKey = crypto.createHash('sha256').update([o.to.toLowerCase(), dynamic ? selector : o.data.toLowerCase(), valueWei.toString()].join('|')).digest('hex').slice(0, 16);
const lockFile = path.join(RUNS, `lock_${lockKey}.json`);
const save = (name, obj) => { try { fs.writeFileSync(path.join(RUNS, `${stamp}_${label}_${name}.json`), typeof obj === 'string' ? obj : L.safeJson(obj)); } catch {} };

// ---- state ----
let decodeIface = null;
let head = { number: 0, ts: 0, at: 0 };
let startUnix = null, startMs = 0, deadline = 0;
let ctx = { wallet: null, agentId: null };
let executing = false, done = false;
let previewsSent = 0, previewsInflight = 0, lastPreviewAt = 0;
let lastSimRevert = null; // { name, cls, at }
let simRounds = 0, simInflight = 0, simOkSeen = false;
const TL = {}; // timeline marks
const mark = (k, t = L.now()) => { if (TL[k] == null) TL[k] = t; };
function printTimeline() {
  if (!startMs || !Object.keys(TL).length) return;
  const row = k => TL[k] != null ? `${k}=${((TL[k] - startMs) / 1000).toFixed(3)}s` : null;
  log('TIMELINE ' + ['firstTrigger', 'previewSent', 'previewOk', 'executeSent', 'broadcast', 'included'].map(row).filter(Boolean).join(' | ') + (TL.includedBlockTs ? ` | includedBlockTs=T+${TL.includedBlockTs - startUnix}s` : ''));
}

// ---- head tracking: WS newHeads + HTTP polling on the fastest RPC ----
let stopWs = () => {};
function onHead(h) { if (h.number > head.number) { head = { number: h.number, ts: h.ts, at: L.now() }; if (startUnix && !o.noEager && h.ts >= startUnix && L.now() < startMs + o.clockFire + o.burst) trigger(`head #${h.number} ts ${h.ts} >= start (${h.url ? L.hostOf(h.url) : 'http'})`, 'head'); } }
async function headPoll(stopAt) {
  while (L.now() < stopAt && !done) {
    try {
      const b = await L.rpc('eth_getBlockByNumber', ['latest', false], { urls: L.fastRpcs(3), timeoutMs: 1500 });
      onHead({ number: parseInt(b.number, 16), ts: parseInt(b.timestamp, 16) });
    } catch {}
    await L.sleep(150);
  }
}

// ---- eth_call spin: fastest 4 RPCs x {latest,pending}, non-blocking rounds ----
function simRound(from, data) {
  const tx = { from, to: o.to, data, value: '0x' + valueWei.toString(16) };
  simRounds++; simInflight++;
  const urls = L.fastRpcs(4);
  const jobs = []; for (const u of urls) for (const tag of ['latest', 'pending']) jobs.push([u, tag]);
  let left = jobs.length, bestRevert = null, settled = false;
  const finish = () => { if (settled) return; settled = true; simInflight--; if (bestRevert) onSimRevert(bestRevert); };
  const t = setTimeout(finish, 1500);
  for (const [u, tag] of jobs) {
    L.rpcOne(u, 'eth_call', [tx, tag], 1500).then(
      () => { if (!settled) { settled = true; simInflight--; clearTimeout(t); if (o.gateSim && startMs && L.now() < startMs) { if (!simOkSeen) log('gateSim: eth_call OK before start ignored'); simOkSeen = true; return; } simOkSeen = true; trigger(`eth_call OK (${L.hostOf(u)} ${tag})`, 'sim'); } },
      e => {
        // prefer a revert that carries data (decodable) over a data-less one
        if (L.isRevert(e) && (!bestRevert || (!bestRevert.hasData && L.hasRevertData(e)))) bestRevert = { error: e, url: u, tag, hasData: L.hasRevertData(e) };
        if (--left === 0) { clearTimeout(t); finish(); }
      });
  }
}
let lastLogName = '';
async function onSimRevert({ error, url, tag, hasData }) {
  const d = await L.decodeRevert(error, decodeIface);
  let c = L.classify(d.name, { waitRe: o.waitOn, fatalRe: o.fatalOn });
  const tnow = L.now();
  // a data-less revert (node stripped it) is never enough to stop: keep waiting until --timeout
  if (c === 'unknown') c = (!hasData || !startMs || tnow < startMs + o.grace * 1000) ? 'wait' : 'fatal';
  if (c === 'fatal' && !hasData && !d.isString) c = 'wait';
  // before start, only hard-terminal names count as fatal (a pre-start sim can hit odd branches)
  if (startMs && tnow < startMs && c === 'fatal' && !/sold|gone|already|taken|used|agent|eligible|expired|ended|minted.?out/i.test(d.name)) c = 'wait';
  const nm = `${d.name}${d.sel ? ' ' + d.sel : ''}`;
  lastSimRevert = { name: nm, cls: c, at: tnow };
  if (nm !== lastLogName || simRounds % 50 === 0) { log(`sim #${simRounds} REVERT ${nm} [${c}] (${L.hostOf(url)} ${tag}) head #${head.number} ts ${head.ts}`); lastLogName = nm; }
  if (c === 'fatal' && !executing) die(`terminal revert: ${nm}${d.args ? ' ' + d.args.join(',') : ''} — not sending`);
}

// ---- preview scheduler ----
let triggerReasons = new Set();
function trigger(reason, kind) {
  if (done || executing) return;
  mark('firstTrigger');
  if (!triggerReasons.has(kind)) { triggerReasons.add(kind); log(`TRIGGER ${reason}`); }
  if (o.dry && o.noPreview) { log(`DRY: would preview+execute now. value ${valueWei}`); done = true; printTimeline(); process.exit(0); }
  const tnow = L.now();
  if (previewsInflight >= o.inflight) return;
  if (tnow - lastPreviewAt < o.gap) return;
  if (previewsSent >= o.maxPreviews) return die(`gave up after ${previewsSent} previews without a successful simulation`);
  if (o.once && previewsSent >= 1) return;
  lastPreviewAt = tnow; previewsSent++; previewsInflight++;
  runPreview(previewsSent, reason).catch(e => log('preview ERR ' + (e.stack || e.message))).finally(() => previewsInflight--);
}
async function runPreview(n, reason) {
  const data = await buildData(ctx);
  const args = ['contract-call', 'preview', '--binanceChainId', '56', '--from', ctx.wallet, '--to', o.to, '--value', valueWei.toString(), '--inputData', data];
  if (o.gasLimit) args.push('--gasLimit', String(o.gasLimit));
  const t0 = L.now(); mark('previewSent', t0);
  const pr = await L.baw(args, 30000);
  save(`preview${n}`, pr.stdout || pr.stderr);
  const ck = checkPreview(pr);
  log(`preview #${n} ${pr.ms}ms → ${ck.verdict}${ck.why ? ' ' + ck.why.slice(0, 400) : ''}${ck.requestId ? ' requestId ' + ck.requestId.slice(0, 10) + '… requireConfirmation ' + ck.requireConfirmation + ' gas ' + ck.gas : ''}`);
  if (ck.caution && ck.caution.length) log('preview CAUTION (non-blocking):', L.safeJson(ck.caution));
  if (ck.verdict === 'ok') { mark('previewOk'); return execute(ck, data, n); }
  if (done || executing) return;
  const tnow = L.now();
  if (ck.verdict === 'wait' || (ck.verdict === 'unknown' && startMs && tnow < startMs + o.grace * 1000)) {
    if (o.once) die('--once: preview not ready, not retrying');
    // keep the pressure on: if a trigger condition still holds, the next tick re-triggers after --gap
    return;
  }
  die(ck.why || 'preview failed');
}
function classifyText(txt) {
  const names = (txt.match(/\b[A-Z][A-Za-z]{3,40}\b/g) || []);
  for (const n of names) { const c = L.classify(n, { waitRe: o.waitOn, fatalRe: o.fatalOn }); if (c !== 'unknown') return c; }
  return L.classify(txt, { waitRe: o.waitOn, fatalRe: o.fatalOn }) === 'wait' ? 'wait' : 'unknown';
}
function nativeOutflowWei(sim) {
  let max = null;
  for (const b of (sim && sim.balanceChanges) || []) {
    const s = JSON.stringify(b).toLowerCase();
    if (!/0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee|"bnb"|native/.test(s)) continue;
    for (const k of ['amount', 'change', 'value', 'delta', 'balanceChange', 'rawAmount']) {
      if (b[k] == null) continue;
      try { let v = String(b[k]); if (/[.eE]/.test(v)) continue; let w = BigInt(v.replace(/^-/, '')); if (max == null || w > max) max = w; } catch {}
    }
  }
  return max;
}
function checkPreview(r) {
  const j = r.json || {};
  if (!r.ok || !j.data) {
    const e = j.error || {};
    const txt = L.safeJson(j.error || r.stdout || r.stderr).slice(0, 600);
    if (e.code === 351803 || /RISK_BLOCKED/i.test(e.name || '')) return { verdict: 'fatal', why: `Binance risk block ${e.code} ${e.name}: ${e.message} — not bypassing` };
    if (e.code === 351802 || e.code === 351804 || /dev.?mode/i.test(txt)) return { verdict: 'fatal', why: 'Developer Mode off/expired (enable in Binance App) ' + txt };
    if (/UNCONNECTED|not.?log|unauth|sign.?in|SSL_ERROR/i.test(txt)) return { verdict: 'fatal', why: 'wallet session/network problem — do NOT auth signin automatically; ask the user ' + txt };
    if (e.code === 351805) {
      // backend simulation failed: before/around start that is just "not open yet"; after grace use the eth_call verdict
      const c = classifyText(txt);
      if (c !== 'unknown') return { verdict: c, why: 'sim failed: ' + txt };
      if (lastSimRevert && L.now() - lastSimRevert.at < 3000) return { verdict: lastSimRevert.cls === 'fatal' ? 'fatal' : 'wait', why: `sim failed (eth_call says ${lastSimRevert.name} [${lastSimRevert.cls}])` };
      return { verdict: 'unknown', why: 'sim failed: ' + txt };
    }
    return { verdict: classifyText(txt), why: 'preview error ' + txt };
  }
  const d = j.data, sim = d.simulationResult || {};
  if (sim.simulationCode !== '000000000') {
    const txt = L.safeJson(sim).slice(0, 600);
    return { verdict: classifyText(txt), why: `preview simulationCode ${sim.simulationCode} ${txt}` };
  }
  if ((sim.allowanceChanges || []).length || (sim.authorityChanges || []).length)
    return { verdict: 'fatal', why: 'preview shows allowance/authority changes — not executing ' + L.safeJson({ a: sim.allowanceChanges, au: sim.authorityChanges }) };
  const risks = d.risks || {};
  const hard = (risks.riskDetails || []).filter(x => String(x.riskType).toUpperCase() === 'RISK');
  const addrHard = Object.entries(risks.addresses || {}).filter(([, v]) => (v.riskDetails || []).some(x => String(x.riskType).toUpperCase() === 'RISK'));
  if (hard.length || addrHard.length) return { verdict: 'fatal', why: 'preview RISK flags — needs user review: ' + L.safeJson({ hard, addrHard }) };
  const out = nativeOutflowWei(sim);
  if (out != null && out > maxWei + ethers.parseEther('0.003')) return { verdict: 'fatal', why: `native outflow ${ethers.formatEther(out)} BNB > cap` };
  if (d.parsedTx && d.parsedTx.amount != null && /^\d+$/.test(String(d.parsedTx.amount)) && (d.parsedTx.contractAddress == null || /0xeeee/i.test(d.parsedTx.contractAddress)) && valueWei === 0n && BigInt(d.parsedTx.amount) > 0n)
    return { verdict: 'fatal', why: 'parsedTx amount > 0 on a value-0 call: ' + L.safeJson(d.parsedTx) };
  if (!d.requestId) return { verdict: 'fatal', why: 'no requestId in preview' };
  if (o.expectNft != null) {
    const me = String(ctx.wallet || '').toLowerCase();
    const nfts = (sim.balanceChanges || []).filter(b => /erc721|erc1155/i.test(String(b.tokenType)) && String(b.owner || '').toLowerCase() === me && String(b.contractAddress || '').toLowerCase() === o.to.toLowerCase() && Number(b.change) > 0);
    const n = nfts.reduce((s, b) => s + Number(b.change), 0);
    if (n !== o.expectNft) return { verdict: 'fatal', why: `preview shows ${n} NFT(s) arriving, expected ${o.expectNft}: ` + L.safeJson(sim.balanceChanges).slice(0, 400) };
  }
  const caution = (risks.riskDetails || []).filter(x => String(x.riskType).toUpperCase() !== 'RISK');
  return { verdict: 'ok', requestId: d.requestId, requireConfirmation: !!d.requireConfirmation, caution, gas: sim.gasTokenFromData, balanceChanges: sim.balanceChanges };
}

// ---- execute exactly once ----
async function execute(ck, data, n) {
  if (executing || done) { log(`preview #${n} OK but another execute is already in flight — ignored`); return; }
  executing = true;
  if (o.dry) { log(`DRY: stop before execute. Would run: baw contract-call execute --requestId ${ck.requestId} --json`); done = true; printTimeline(); process.exit(0); }
  if (fs.existsSync(lockFile)) die('lock appeared — another run executed this call');
  fs.writeFileSync(lockFile, L.safeJson({ t: L.wib(), to: o.to, data, value: valueWei, requestId: ck.requestId, state: 'executing' }));
  mark('executeSent');
  const ex = await L.baw(['contract-call', 'execute', '--requestId', ck.requestId], 90000);
  save('exec', ex.stdout || ex.stderr);
  const ed = ex.json && ex.json.data;
  fs.writeFileSync(lockFile, L.safeJson({ t: L.wib(), to: o.to, data, value: valueWei, requestId: ck.requestId, state: ed ? ed.status : 'exec_error', exec: ex.json || ex.stdout }));
  done = true; stopWs();
  if (!ex.ok || !ed) {
    log(`EXECUTE ERROR (${ex.ms}ms) — NOT retrying. ${L.safeJson(ex.json || ex.stdout || ex.stderr).slice(0, 800)}`);
    log('Check `baw wallet tx-history --json` / `baw wallet tx-lock --json` before any manual retry.');
    printTimeline(); process.exit(1);
  }
  mark('broadcast');
  log(`EXECUTE ${ed.status} (${ex.ms}ms) orderId ${ed.orderId} txHash ${ed.txHash || '-'} ${ed.message || ''}`);
  if (ed.status === 'PENDING_CONFIRMATION' || !ed.txHash) { log('Needs approval in the Binance App (abnormal/large tx). Not resending.'); printTimeline(); process.exit(0); }
  log(`BscScan ${L.SCAN}/tx/${ed.txHash}`);
  const rc = await receipt(ed.txHash);
  if (!rc) { log('receipt not found in 120s — check BscScan; NOT resending'); printTimeline(); process.exit(0); }
  const st = parseInt(rc.status, 16);
  save('receipt', rc);
  mark('included');
  try { const b = await L.rpc('eth_getBlockByNumber', [rc.blockNumber, false], { timeoutMs: 3000 }); TL.includedBlockTs = parseInt(b.timestamp, 16); } catch {}
  log(`RECEIPT ${st === 1 ? 'SUCCESS' : 'REVERTED'} block ${parseInt(rc.blockNumber, 16)} gasUsed ${parseInt(rc.gasUsed, 16)} logs ${rc.logs.length} | ${L.SCAN}/tx/${ed.txHash}`);
  printTimeline();
  process.exit(st === 1 ? 0 : 1);
}
async function receipt(hash) {
  const until = L.now() + 120000;
  while (L.now() < until) {
    try { const r = await L.rpc('eth_getTransactionReceipt', [hash], { urls: L.fastRpcs(4), timeoutMs: 2500 }); if (r) return r; } catch {}
    await L.sleep(200);
  }
  return null;
}

// ---- main ----
(async () => {
  const clk = await L.syncClock();
  startUnix = L.parseStart(o.start);
  startMs = (startUnix || 0) * 1000;
  if (startMs) L.setT0(startMs);
  log(`FIRE ${label} to=${o.to} value=${o.value} BNB (${valueWei} wei) cap=${ethers.formatEther(maxWei)} BNB ${o.sig ? 'sig=' + o.sig + ' args=' + L.safeJson(rawArgs) + (dynamic ? ' [DYNAMIC]' : '') : 'data=' + (o.data.length > 140 ? o.data.slice(0, 140) + '…' : o.data)}${o.dry ? ' [DRY]' : ''}${o.once ? ' [ONCE]' : ''}`);
  log(`clock offset ${clk.offsetMs >= 0 ? '+' : ''}${clk.offsetMs}ms (${clk.source})`);
  if (startUnix) log(`start ${startUnix} = ${L.fmtUnix(startUnix)}${startMs < L.now() ? ' (already passed → fire now)' : ` (in ${((startMs - L.now()) / 1000).toFixed(1)}s)`}`);
  if (fs.existsSync(lockFile) && !o.dry) die(`lock exists ${lockFile} — this exact call was already executed. Never auto-repeat. Delete the lock only on the user's explicit new command.`);

  // ---- precheck (parallel) ----
  const [status, addr, settings, warm] = await Promise.all([
    L.bawStatus(), o.from ? Promise.resolve(ethers.getAddress(o.from)) : L.bawEvmAddress(), L.baw(['wallet', 'settings']), L.warmRpcs(),
  ]);
  log(`baw status ${status} | from ${addr} | rpc ${warm.slice(0, 6).map(w => `${L.hostOf(w.u)}:${w.err ? 'ERR' : w.ms + 'ms' + (w.lag ? ' lag' + w.lag : '')}`).join(' ')}`);
  if (status !== 'CONNECTED') die(`baw wallet status = ${status}. Not running auth signin. Ask the user to reconnect (auth signin is a user-approved step).`);
  if (!addr) die('could not read wallet address');
  ctx.wallet = addr;
  const dm = settings.json && settings.json.data && settings.json.data.devMode;
  if (!dm || !dm.enabled || (dm.expiresAt && Date.parse(dm.expiresAt) < Date.now())) die('Developer Mode is off/expired — user must enable it in the Binance App (Agentic Wallet → Settings → Developer Mode).');
  log(`devMode on until ${dm.expiresAt}; devMode quota used today ${settings.json.data.developerModeQuotaUsed} / ${dm.dailyLimit} USD; session until ${settings.json.data.sessionExpireTime}`);
  const [code, bal, agent, ab] = await Promise.all([
    L.rpc('eth_getCode', [o.to, 'latest']), L.rpc('eth_getBalance', [addr, 'latest']),
    L.agentIdOf(addr).catch(() => null), L.sourcifyAbiCached(ethers.getAddress(o.abi || o.to)),
  ]);
  if (!code || code === '0x') die(`${o.to} has no code on BSC`);
  const balWei = BigInt(bal);
  log(`balance ${ethers.formatEther(balWei)} BNB | agentId ${agent && agent.handle ? agent.handle + '.ai ' + agent.tokenId : 'NONE'}`);
  if (balWei < valueWei + ethers.parseEther('0.0003')) die('balance too low for value + gas');
  if (agent && agent.tokenId != null) ctx.agentId = agent.tokenId;
  if (ab) { try { decodeIface = new ethers.Interface(ab.abi); log(`sourcify ABI loaded (${ab.match}), ${decodeIface.fragments.filter(f => f.type === 'error').length} errors`); } catch {} }
  const data0 = await buildData(ctx);
  if (decodeIface) { try { const f = decodeIface.getFunction(data0.slice(0, 10)); if (f) log(`call = ${f.format('sighash')}${f.payable ? ' payable' : ''} args ${L.safeJson(decodeIface.decodeFunctionData(f, data0))}`); else log('WARN selector not in verified ABI'); } catch { log('WARN selector not in verified ABI'); } }
  if (dynamic) log(`dynamic calldata now: ${data0.slice(0, 140)}${data0.length > 140 ? '…' : ''}`);

  // ---- wait until start - lead (re-check session at T-20s, re-rank RPCs at T-10s) ----
  deadline = (startMs || L.now()) + o.timeout * 1000;
  let did20 = false, did10 = false;
  while (startMs && L.now() < startMs - o.lead) {
    const left = startMs - L.now();
    if (!did20 && left < 20000) { did20 = true; const s = await L.bawStatus(); log(`T-${(left / 1000).toFixed(0)}s baw status ${s}`); if (s !== 'CONNECTED') die('session dropped before start'); }
    if (!did10 && left < 10000) { did10 = true; const w = await L.warmRpcs(); log(`T-${(left / 1000).toFixed(0)}s rpc re-ranked: ${w.slice(0, 4).map(x => L.hostOf(x.u) + ':' + x.ms + 'ms').join(' ')}`); await L.syncClock(); }
    await L.sleep(Math.min(500, Math.max(10, startMs - o.lead - L.now())));
  }

  // ---- spin ----
  if (!o.noWs) stopWs = L.wsHeads(onHead);
  headPoll(deadline + 5000);
  log(`spinning: eth_call latest+pending x ${L.fastRpcs(4).map(u => L.hostOf(u)).join(',')} every ${o.interval}ms; triggers: sim${o.noEager ? '' : ', head.ts>=start'}${o.clockFire >= 0 && startMs ? ', clock@start+' + o.clockFire + 'ms' : ''}`);
  if (!startMs) trigger('no --start: fire now', 'now');
  let clockFired = false;
  for (;;) {
    if (done) { await L.sleep(1000); continue; }
    const tnow = L.now();
    if (tnow > deadline) die(`timeout ${o.timeout}s after start, still not mintable`);
    if (!executing) {
      if (simInflight < 3) { try { simRound(addr, dynamic ? await buildData(ctx) : data0); } catch (e) { log('sim build ERR ' + e.message); } }
      // burst window: clock + head keep previews flowing for --burst ms after start; after that only an eth_call OK
      // (a public node seeing the open state) launches a preview, so a late-opening sale is not spammed into --maxPreviews
      const inBurst = startMs && tnow < startMs + o.clockFire + o.burst;
      if (inBurst && o.clockFire >= 0 && tnow >= startMs + o.clockFire) { if (!clockFired) { clockFired = true; } trigger(`clock ${L.tplus(tnow)} >= start+${o.clockFire}ms`, 'clock'); }
      if (inBurst && !o.noEager && head.ts >= startUnix) trigger(`head #${head.number} ts ${head.ts} >= start`, 'head');
      if (o.once && previewsSent >= 1 && previewsInflight === 0 && !executing) die('--once: preview did not succeed, not retrying');
    }
    await L.sleep(o.interval);
  }
})().catch(e => { log('ERR ' + (e.stack || e.message)); printTimeline(); process.exit(1); });
