// fastmint shared helpers: TLS bootstrap, ranked RPC pool (race), WebSocket heads, clock sync,
// WIB logging, revert decoding, baw runner, Agent ID lookup, Sourcify ABI cache.
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile, spawnSync } = require('child_process');

// ---------- TLS bootstrap ----------
// Node's bundled CA store fails on this machine (UNABLE_TO_GET_ISSUER_CERT_LOCALLY) while curl works.
// bench.js --ca builds a PEM from the macOS keychain; if present and not yet loaded, re-exec with it.
const CA_PEM = process.env.FASTMINT_CA || path.join(os.homedir(), '.config', 'certs', 'system-ca.pem');
if (!process.env.NODE_EXTRA_CA_CERTS && !process.env.__FM_REEXEC && fs.existsSync(CA_PEM)) {
  const r = spawnSync(process.execPath, [...process.execArgv, ...process.argv.slice(1)], {
    stdio: 'inherit', env: { ...process.env, NODE_EXTRA_CA_CERTS: CA_PEM, __FM_REEXEC: '1' },
  });
  process.exit(r.status == null ? 1 : r.status);
}

const ethers = require('./ethers.umd.min.js');

const CHAIN_ID = 56;
// Ordered by measured latency from Indonesia (bench.js). warmRpcs() re-ranks in place at runtime.
// (api.zan.top is fast but strips revert data → "Unknown" reverts; left out of the default pool.)
const DEFAULT_RPCS = [
  'https://rpc-bsc.48.club',
  'https://bsc.rpc.blxrbdn.com',
  'https://0.48.club',
  'https://bsc-dataseed.bnbchain.org',
  'https://bsc-dataseed1.ninicoin.io',
  'https://bsc-dataseed1.binance.org',
  'https://bsc.blockrazor.xyz',
  'https://bsc-dataseed2.defibit.io',
  'https://bsc-rpc.publicnode.com',
];
// FASTMINT_RPCS replaces the pool; FASTMINT_RPCS_EXTRA (e.g. a premium endpoint with a key, kept in .env) is prepended
// and still auto-ranked. Same for FASTMINT_WS / FASTMINT_WS_EXTRA. URLs with keys are masked in logs by hostOf().
const splitList = s => String(s || '').split(',').map(x => x.trim()).filter(Boolean);
const RPCS = [...new Set([...splitList(process.env.FASTMINT_RPCS_EXTRA), ...(process.env.FASTMINT_RPCS ? splitList(process.env.FASTMINT_RPCS) : DEFAULT_RPCS)])];
const WS_RPCS = [...new Set([...splitList(process.env.FASTMINT_WS_EXTRA), ...splitList(process.env.FASTMINT_WS || 'wss://bsc-rpc.publicnode.com,wss://bsc.drpc.org')])];
const hostOf = u => { try { return new URL(u).host; } catch { return String(u).slice(0, 30); } };
const AGENT_REGISTRY = '0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F';
const SCAN = 'https://bscscan.com';
const TZ = process.env.FASTMINT_TZ || 'Asia/Jakarta';
const TZ_LABEL = process.env.FASTMINT_TZ_LABEL || (TZ === 'Asia/Jakarta' ? 'WIB' : TZ);

// ---------- clock ----------
// offsetMs = (true time) - (local Date.now()). Set by syncClock(). now() returns corrected ms.
let offsetMs = 0;
const now = () => Date.now() + offsetMs;
async function syncClock() {
  // macOS/BSD sntp prints "+0.104913 +/- 0.07 host ip"; Linux may have ntpdate -q. Falls back to 0.
  const tries = [['sntp', ['-t', '2', 'time.apple.com']], ['sntp', ['-t', '2', 'pool.ntp.org']]];
  for (const [bin, args] of tries) {
    const r = spawnSync(bin, args, { encoding: 'utf8', timeout: 6000 });
    const m = String(r.stdout || '').match(/^\s*([+-]\d+\.\d+)/m);
    if (m) { offsetMs = Math.round(parseFloat(m[1]) * 1000); return { offsetMs, source: args[2] }; }
  }
  return { offsetMs: 0, source: 'none' };
}
function getOffsetMs() { return offsetMs; }

// ---------- time ----------
function wib(d = new Date(now())) {
  const s = d.toLocaleString('sv-SE', { timeZone: TZ });
  return s + '.' + String(d.getMilliseconds()).padStart(3, '0') + ' ' + TZ_LABEL;
}
let LOGFILE = null;
function setLogFile(f) { LOGFILE = f; }
let T0 = null; // start ms (corrected) for T+ offsets in logs
function setT0(ms) { T0 = ms; }
function tplus(ms = now()) { if (!T0) return ''; const d = (ms - T0) / 1000; return (d >= 0 ? 'T+' : 'T') + d.toFixed(3) + 's'; }
function log(...a) {
  const t = now();
  const line = `[${wib(new Date(t))}${T0 ? ' ' + tplus(t) : ''}] ` + a.map(x => typeof x === 'string' ? x : safeJson(x)).join(' ');
  console.log(line);
  if (LOGFILE) try { fs.appendFileSync(LOGFILE, line + '\n'); } catch {}
}
function safeJson(x) {
  try { return JSON.stringify(x, (k, v) => typeof v === 'bigint' ? v.toString() : v); } catch { return String(x); }
}
// "HH:MM" or "HH:MM:SS" (local TZ, today; if >12h in the past → tomorrow), unix seconds, or ISO-8601.
function parseStart(s) {
  if (s == null || s === '') return null;
  s = String(s).trim();
  if (/^\d{9,11}$/.test(s)) return Number(s);
  if (/^\d{12,14}$/.test(s)) return Math.floor(Number(s) / 1000); // ms
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) { const t = Date.parse(s); if (!isNaN(t)) return Math.floor(t / 1000); }
  const m = s.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (!m) throw new Error('bad --start (use unix seconds, HH:MM[:SS] ' + TZ_LABEL + ', or ISO-8601): ' + s);
  const tzOff = tzOffsetMs();
  const nowTz = new Date(now() + tzOff);
  let t = Date.UTC(nowTz.getUTCFullYear(), nowTz.getUTCMonth(), nowTz.getUTCDate(), +m[1], +m[2], +(m[3] || 0)) - tzOff;
  if (t < now() - 12 * 3600e3) t += 24 * 3600e3;
  return Math.floor(t / 1000);
}
function tzOffsetMs(d = new Date()) {
  // offset of TZ from UTC at date d (handles DST for non-WIB zones)
  const f = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const p = Object.fromEntries(f.formatToParts(d).map(x => [x.type, x.value]));
  const asUtc = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute, +p.second);
  return asUtc - Math.floor(d.getTime() / 1000) * 1000;
}
function fmtUnix(u) { return wib(new Date(Number(u) * 1000)).replace('.000', ''); }
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ---------- RPC ----------
let rpcId = 1;
async function rpcOne(url, method, params, timeoutMs = 4000) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(url, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: rpcId++, method, params }), signal: ctl.signal,
    });
    const j = await r.json();
    if (j.error) { const e = new Error(j.error.message || 'rpc error'); e.rpcError = j.error; e.url = url; throw e; }
    return j.result;
  } finally { clearTimeout(t); }
}
// Is this an execution revert (deterministic) vs transport/rate-limit noise?
function isRevert(e) {
  const er = e && e.rpcError;
  if (!er) return false;
  if (er.data !== undefined && er.data !== null && er.data !== '') return true;
  return /revert|execution|invalid opcode|out of gas|insufficient funds/i.test(er.message || '');
}
// A revert that carries return data is deterministic; one without (some nodes strip it) is weak evidence.
function hasRevertData(e) { const d = e && e.rpcError && e.rpcError.data; return typeof d === 'string' ? d.length > 2 : !!(d && typeof d.data === 'string' && d.data.length > 2); }
// Race RPCs: first success wins; first revert *with data* also wins. Data-less reverts and transport errors
// only count once every endpoint has answered (then the best revert, else reject).
function rpcRace(method, params, { urls = RPCS, timeoutMs = 4000 } = {}) {
  return new Promise((resolve, reject) => {
    let left = urls.length, lastErr, weakRevert = null;
    for (const u of urls) {
      rpcOne(u, method, params, timeoutMs).then(
        res => resolve({ ok: true, result: res, url: u }),
        err => {
          if (isRevert(err)) { if (hasRevertData(err)) return resolve({ ok: false, error: err, url: u }); if (!weakRevert) weakRevert = { ok: false, error: err, url: u, weak: true }; }
          else lastErr = err;
          if (--left === 0) { if (weakRevert) resolve(weakRevert); else reject(lastErr || new Error('all rpc failed')); }
        });
    }
  });
}
async function rpc(method, params, opts) {
  const r = await rpcRace(method, params, opts);
  if (!r.ok) throw r.error;
  return r.result;
}
// Measures every RPC (2 rounds, warm), re-orders RPCS in place fastest-first, drops dead ones to the end.
async function warmRpcs({ rounds = 2, keep = RPCS.length } = {}) {
  const stats = new Map(RPCS.map(u => [u, { u, ms: [], block: 0, err: null }]));
  for (let i = 0; i < rounds; i++) {
    await Promise.all(RPCS.map(async u => {
      const s = Date.now(), st = stats.get(u);
      try { const b = await rpcOne(u, 'eth_blockNumber', [], 4000); st.ms.push(Date.now() - s); st.block = parseInt(b, 16); }
      catch (e) { st.err = (e.message || '').slice(0, 50); }
    }));
  }
  const res = [...stats.values()].map(s => ({ u: s.u, ms: s.ms.length ? Math.min(...s.ms) : 9999, block: s.block, err: s.ms.length ? null : s.err }));
  res.sort((a, b) => a.ms - b.ms);
  const maxBlock = Math.max(...res.map(r => r.block));
  for (const r of res) r.lag = r.block ? maxBlock - r.block : null;
  // stale nodes (>2 blocks behind) sink below healthy ones
  res.sort((a, b) => ((a.err ? 1 : 0) - (b.err ? 1 : 0)) || ((a.lag > 2 ? 1 : 0) - (b.lag > 2 ? 1 : 0)) || a.ms - b.ms);
  RPCS.splice(0, RPCS.length, ...res.map(r => r.u));
  return res.slice(0, keep);
}
const fastRpcs = n => RPCS.slice(0, n);

// ---------- WebSocket newHeads ----------
// onHead({number, ts, url, recvMs}) for every new head from each WS endpoint. Returns close().
function wsHeads(onHead, urls = WS_RPCS) {
  const socks = [];
  for (const u of urls) {
    try {
      const ws = new WebSocket(u);
      ws.onopen = () => ws.send(JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_subscribe', params: ['newHeads'] }));
      ws.onmessage = m => {
        try {
          const j = JSON.parse(m.data);
          if (j.params && j.params.result) { const h = j.params.result; onHead({ number: parseInt(h.number, 16), ts: parseInt(h.timestamp, 16), url: u, recvMs: now() }); }
        } catch {}
      };
      ws.onerror = () => {};
      socks.push(ws);
    } catch {}
  }
  return () => { for (const s of socks) try { s.close(); } catch {} };
}

// ---------- revert decoding ----------
const STD_ERRORS = [
  'error Error(string)', 'error Panic(uint256)',
  ...['NotStarted', 'NotOpen', 'NotOpened', 'NotLive', 'NotActive', 'SaleNotStarted', 'MintNotStarted', 'MintNotOpen', 'TooEarly', 'SaleNotActive', 'Paused', 'EnforcedPause', 'NotYet', 'SaleInactive', 'MintInactive', 'PhaseNotStarted',
    'SoldOut', 'FreeSoldOut', 'FreeGone', 'PaidSoldOut', 'MaxSupply', 'ExceedsMaxSupply', 'MaxSupplyReached', 'QuotaExceeded', 'LimitExceeded', 'ExceedsLimit', 'MaxPerWallet', 'MaxPerWalletExceeded', 'MintedOut',
    'AlreadyClaimed', 'AlreadyMinted', 'AlreadyTaken', 'FreeUsed', 'FreeAlreadyClaimed', 'AlreadyBooked', 'AllowanceUsed',
    'AgentIdRequired', 'NoAgentId', 'NotAgent', 'NotEligible', 'NotWhitelisted', 'NotAllowed', 'Unauthorized', 'InvalidProof', 'BadSignature',
    'SaleExpired', 'Ended', 'SaleEnded', 'MintEnded', 'Closed', 'Expired', 'DeadlinePassed',
    'WrongValue', 'WrongPrice', 'InsufficientPayment', 'BadValue', 'InvalidValue', 'BadQty', 'ZeroQty', 'BadStart', 'StartMismatch', 'Slippage', 'BadInviter', 'SelfInvite', 'NoShares', 'NothingToCollect']
    .map(n => `error ${n}()`),
];
const stdIface = new ethers.Interface(STD_ERRORS);
const sigCache = new Map();
async function lookupSelector(sel) {
  if (sigCache.has(sel)) return sigCache.get(sel);
  let name = null;
  try {
    const ctl = new AbortController(); setTimeout(() => ctl.abort(), 3000);
    const r = await fetch(`https://api.4byte.sourcify.dev/signature-database/v1/lookup?function=${sel}&filter=true`, { signal: ctl.signal });
    const j = await r.json();
    const arr = j && j.result && j.result.function && j.result.function[sel];
    if (arr && arr.length) name = arr[0].name;
  } catch {}
  if (!name) try {
    const ctl = new AbortController(); setTimeout(() => ctl.abort(), 3000);
    const r = await fetch(`https://www.4byte.directory/api/v1/signatures/?hex_signature=${sel}`, { signal: ctl.signal });
    const j = await r.json();
    if (j.results && j.results.length) name = j.results[j.results.length - 1].text_signature;
  } catch {}
  sigCache.set(sel, name);
  return name;
}
// Returns {name, sel, raw, args, msg}
async function decodeRevert(err, extraIface) {
  const er = (err && err.rpcError) || {};
  let raw = typeof er.data === 'string' ? er.data : (er.data && typeof er.data.data === 'string' ? er.data.data : '');
  if (!raw) { const m = String(er.message || err.message || '').match(/0x[0-9a-fA-F]{8,}/); if (m) raw = m[0]; }
  const msg = String(er.message || err.message || '');
  if (!raw || raw === '0x') {
    const m = msg.match(/reverted:?\s*(.*)$/i);
    return { name: m && m[1] ? m[1].trim() : 'Unknown', sel: null, raw: raw || '', msg };
  }
  const sel = raw.slice(0, 10).toLowerCase();
  for (const ifc of [extraIface, stdIface]) {
    if (!ifc) continue;
    try {
      const d = ifc.parseError(raw);
      if (d) {
        if (d.name === 'Error') return { name: String(d.args[0]), sel, raw, msg, isString: true };
        return { name: d.name, sel, raw, args: d.args.map(String), msg };
      }
    } catch {}
  }
  const sig = await lookupSelector(sel);
  return { name: sig ? sig.replace(/\(.*$/, '') : 'Unknown', sig, sel, raw, msg };
}
// Classify a revert name/message: 'wait' (not started yet) | 'fatal' | 'unknown'
const WAIT_RE = /not.?start|not.?open(ed)?$|^notopen$|not.?live|not.?active|inactive|too.?early|before.?start|^paused$|enforcedpause|mint.?closed|sale.?closed|not.?yet|wait/i;
const FATAL_RE = /sold.?out|gone|minted.?out|max.?supply|exceed|limit|already|used|taken|booked|agent.?id|no.?agent|not.?agent|eligible|whitelist|not.?allowed|unauthori|proof|signature|expired|ended|deadline|wrong|insufficient|bad|invalid|zero|slippage|mismatch|self|no.?shares|nothing|panic|quota|cap|low|payment|exceeds balance/i;
function classify(name, { waitRe, fatalRe } = {}) {
  const n = String(name || '');
  if (fatalRe && fatalRe.test(n)) return 'fatal';
  if (waitRe && waitRe.test(n)) return 'wait';
  if (WAIT_RE.test(n)) return 'wait';
  if (FATAL_RE.test(n)) return 'fatal';
  return 'unknown';
}

// ---------- baw ----------
function baw(args, timeoutMs = 60000) {
  return new Promise(resolve => {
    const s = Date.now();
    execFile('baw', [...args, '--json'], { timeout: timeoutMs, maxBuffer: 8 << 20, env: process.env }, (err, stdout, stderr) => {
      const out = String(stdout || ''), ms = Date.now() - s;
      let j = null;
      try { j = JSON.parse(out); } catch { const i = out.indexOf('{'); if (i >= 0) try { j = JSON.parse(out.slice(i)); } catch {} }
      resolve({ ok: !err && j && j.success === true, json: j, stdout: out, stderr: String(stderr || ''), err, ms });
    });
  });
}
async function bawStatus() {
  const r = await baw(['wallet', 'status']);
  return (r.json && r.json.data && r.json.data.status) || 'UNKNOWN';
}
async function bawEvmAddress() {
  const r = await baw(['wallet', 'address']);
  const a = r.json && r.json.data && r.json.data.addresses || [];
  const bsc = a.find(x => String(x.binanceChainId) === '56') || a.find(x => /^0x/.test(x.address));
  return bsc ? ethers.getAddress(bsc.address) : null;
}

// ---------- Agent ID ----------
const regIface = new ethers.Interface(['function handleOf(address) view returns (string)', 'function ownerOf(uint256) view returns (address)']);
async function agentIdOf(wallet) {
  const res = await rpc('eth_call', [{ to: AGENT_REGISTRY, data: regIface.encodeFunctionData('handleOf', [wallet]) }, 'latest']);
  const handle = regIface.decodeFunctionResult('handleOf', res)[0];
  if (!handle) return { handle: '', tokenId: null };
  return { handle, tokenId: BigInt(ethers.id(handle)) }; // tokenId = uint256(keccak256(handle))
}

// ---------- Sourcify ----------
async function sourcifyAbi(addr, timeoutMs = 6000) {
  try {
    const ctl = new AbortController(); setTimeout(() => ctl.abort(), timeoutMs);
    const r = await fetch(`https://sourcify.dev/server/v2/contract/${CHAIN_ID}/${addr}?fields=abi`, { signal: ctl.signal });
    if (!r.ok) return null;
    const j = await r.json();
    return j.abi ? { abi: j.abi, match: j.match || j.runtimeMatch || 'verified' } : null;
  } catch { return null; }
}
const cacheDir = path.join(__dirname, 'cache');
async function sourcifyAbiCached(addr) {
  fs.mkdirSync(cacheDir, { recursive: true });
  const f = path.join(cacheDir, `abi_${addr.toLowerCase()}.json`);
  if (fs.existsSync(f)) try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch {}
  const a = await sourcifyAbi(addr);
  if (a) fs.writeFileSync(f, JSON.stringify(a));
  return a;
}

module.exports = {
  ethers, CHAIN_ID, RPCS, WS_RPCS, AGENT_REGISTRY, SCAN, TZ, TZ_LABEL, CA_PEM, hostOf,
  now, syncClock, getOffsetMs, wib, log, setLogFile, setT0, tplus, safeJson, parseStart, fmtUnix, sleep,
  rpcOne, rpcRace, rpc, warmRpcs, fastRpcs, wsHeads, isRevert, hasRevertData, decodeRevert, classify, lookupSelector,
  baw, bawStatus, bawEvmAddress, agentIdOf, sourcifyAbi, sourcifyAbiCached,
};
