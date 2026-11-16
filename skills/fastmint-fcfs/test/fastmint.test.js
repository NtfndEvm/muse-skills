// Offline tests for fastmint-fcfs (node:test, no dependencies).
//
// What is covered (brief item 12 priorities):
//   1. guard value > maxValue refuses
//   2. value > 0 without a cap refuses
//   3. lock file prevents a second broadcast
//   4. --expectNft (satisfied and not satisfied)
//   5. dynamic arg parsing: $agentId, $now+1800, {"getter":...}, $wallet
//   6. brief item 15: unverified contract refuses without --allowUnverified
//      (recon.js prints the red UNVERIFIED flag + pre-open GATE line;
//      fire.js refuses unless --allowUnverified is passed)
//   7. brief item 16: recon.js runs the pre-open gates automatically
//      (verified ABI, not owned, price 0, eth_call sim) and reports them
//   8. brief item 17: --expectNft warning when the count is unknown,
//      ~400000 gas cap (--gasLimit and preview gas estimate), and two
//      parallel fire.js processes execute exactly once (atomic 'wx' lock)
//
// How it stays offline: fire.js runs in a temp dir (copies of fire.js /
// lib.js + a symlink to the bundled ethers) against a local JSON-RPC stub
// server (FASTMINT_RPCS) and a stub `baw` (test/stub-baw.js) on PATH.
// No network, no real baw, no broadcast. Run from the skill folder as
// `node --test test/fastmint.test.js` (or plain `node --test`, discovery).
// NOTE: `node --test test/` FAILS with MODULE_NOT_FOUND on Node v24 —
// do not use that form. Each fire run takes a few seconds (sourcify
// lookup in fire.js has a 6s abort timeout when it cannot be reached).
//
// NOT covered (needs a refactor first, noted not skipped silently):
//   - recon.js argGuess(): internal, not exported.
//   - bench.js --ca: macOS-only (needs the `security` binary); on Linux
//     it writes an empty PEM — see NOTES.md.
//   - checkPreview() branches that need a real baw preview (RISK flags,
//     allowance/authority changes, native outflow): only the --expectNft
//     and gas-estimate branches are reachable through the stub; the rest
//     are unreachable without refactoring checkPreview out of fire.js.
//   - the verified-positive path (Sourcify returns a real ABI): needs
//     network + a real verified contract, so it is not covered offline;
//     only the unverified path is asserted here.
'use strict';
const { describe, it, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

const SKILL_DIR = path.join(__dirname, '..');
const L = require('../lib');
const { ethers } = L;

const WALLET = '0x1111111111111111111111111111111111111111';
const TO = '0x2222222222222222222222222222222222222222';
const REGISTRY = '0x60b9262456de011f7d15a54cdd8c48baaa8b022f';
const DATA = '0x195ad114';

// ---------- local JSON-RPC stub ----------
let rpcServer, rpcUrl;
function rpcResult(id, result) { return { jsonrpc: '2.0', id, result }; }
function startRpc() {
  return new Promise(resolve => {
    rpcServer = http.createServer((req, res) => {
      let body = '';
      req.on('data', c => { body += c; });
      req.on('end', () => {
        let j = {};
        try { j = JSON.parse(body); } catch {}
        const nowHex = '0x' + Math.floor(Date.now() / 1000).toString(16);
        let result = null;
        switch (j.method) {
          case 'eth_blockNumber': result = '0x100'; break;
          case 'eth_getCode': result = '0x60006000'; break;
          case 'eth_getBalance': result = '0x8ac7230489e80000'; break; // 10 BNB
          case 'eth_getBlockByNumber': result = { number: '0x100', timestamp: nowHex }; break;
          case 'eth_getTransactionReceipt':
            result = { blockNumber: '0x100', status: '0x1', gasUsed: '0x5208', logs: [], transactionHash: j.params && j.params[0] };
            break;
          case 'eth_call': {
            const tx = (j.params && j.params[0]) || {};
            const to = String(tx.to || '').toLowerCase();
            const data = String(tx.data || '');
            if (to === REGISTRY) {
              // handleOf(address) -> "alice"
              result = ethers.AbiCoder.defaultAbiCoder().encode(['string'], ['alice']);
            } else if (data.length === 10) {
              // bare 4-byte getter (totalMinted(), saleStart(), ...) -> uint256 41
              result = ethers.AbiCoder.defaultAbiCoder().encode(['uint256'], [41n]);
            } else {
              result = '0x'; // simulation success
            }
            break;
          }
          default: result = null;
        }
        res.writeHead(200, { 'content-type': 'application/json' });
        res.end(JSON.stringify(rpcResult(j.id ?? 1, result)));
      });
    });
    rpcServer.listen(0, '127.0.0.1', () => {
      rpcUrl = `http://127.0.0.1:${rpcServer.address().port}`;
      resolve();
    });
  });
}

before(startRpc);
after(() => { if (rpcServer) rpcServer.close(); });

// ---------- temp workdir with copies of fire.js/lib.js/recon.js + stub baw ----------
function makeWorkdir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'fastmint-test-'));
  fs.copyFileSync(path.join(SKILL_DIR, 'fire.js'), path.join(dir, 'fire.js'));
  fs.copyFileSync(path.join(SKILL_DIR, 'lib.js'), path.join(dir, 'lib.js'));
  fs.copyFileSync(path.join(SKILL_DIR, 'recon.js'), path.join(dir, 'recon.js'));
  fs.symlinkSync(path.join(SKILL_DIR, 'ethers.umd.min.js'), path.join(dir, 'ethers.umd.min.js'));
  const bin = path.join(dir, 'bin');
  fs.mkdirSync(bin);
  fs.copyFileSync(path.join(__dirname, 'stub-baw.js'), path.join(bin, 'baw'));
  fs.chmodSync(path.join(bin, 'baw'), 0o755);
  return { dir, bin, stubLog: path.join(dir, 'stub.log') };
}

// runFire must use async spawn, NOT spawnSync: spawnSync blocks this
// process's event loop, and the local JSON-RPC stub server lives in this
// same process — a blocked loop starves the stub and every fire.js call
// times out. (Learned the hard way: 12/17 failed with spawnSync.)
function runFire(wd, args, extraEnv = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn('node', ['fire.js', ...args], {
      cwd: wd.dir,
      env: {
        ...process.env,
        PATH: wd.bin + path.delimiter + process.env.PATH,
        FASTMINT_RPCS: rpcUrl,
        STUB_WALLET: WALLET,
        STUB_LOG: wd.stubLog,
        ...extraEnv,
      },
      timeout: 120000,
    });
    let stdout = '', stderr = '';
    child.stdout.on('data', d => { stdout += d; });
    child.stderr.on('data', d => { stderr += d; });
    child.on('error', reject);
    child.on('close', status => {
      let stubCalls = [];
      try {
        stubCalls = fs.readFileSync(wd.stubLog, 'utf8').trim().split('\n').filter(Boolean).map(l => JSON.parse(l));
      } catch {}
      resolve({ status, stdout, stderr, stubCalls, dir: wd.dir });
    });
  });
}

// Same harness for recon.js (brief items 15 + 16): read-only, stub RPC +
// stub baw on PATH. Sourcify is NOT stubbed — for the 0x2222... stub
// contract it answers 404 (or times out offline), i.e. unverified.
function runRecon(wd, args, extraEnv = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn('node', ['recon.js', ...args], {
      cwd: wd.dir,
      env: {
        ...process.env,
        PATH: wd.bin + path.delimiter + process.env.PATH,
        FASTMINT_RPCS: rpcUrl,
        STUB_WALLET: WALLET,
        STUB_LOG: wd.stubLog,
        ...extraEnv,
      },
      timeout: 120000,
    });
    let stdout = '', stderr = '';
    child.stdout.on('data', d => { stdout += d; });
    child.stderr.on('data', d => { stderr += d; });
    child.on('error', reject);
    child.on('close', status => resolve({ status, stdout, stderr, dir: wd.dir }));
  });
}

function previewInputData(run) {
  const p = run.stubCalls.find(c => c.argv[0] === 'contract-call' && c.argv[1] === 'preview');
  assert.ok(p, 'stub baw should have received a preview call');
  const i = p.argv.indexOf('--inputData');
  assert.ok(i >= 0, 'preview call should carry --inputData');
  return p.argv[i + 1];
}

function cleanup(wd) { try { fs.rmSync(wd.dir, { recursive: true, force: true }); } catch {} }

// ---------- lib.js pure helpers ----------
describe('lib.js helpers (offline, no network)', () => {
  it('bundled ethers is 6.13.4 and parseEther round-trips', () => {
    assert.equal(ethers.version, '6.13.4');
    assert.equal(ethers.parseEther('0.01').toString(), '10000000000000000');
    assert.equal(ethers.formatEther(ethers.parseEther('0.01')), '0.01');
  });

  it('parseStart passes unix seconds through and parses HH:MM + ISO', () => {
    assert.equal(L.parseStart('1794330000'), 1794330000);
    const t = L.parseStart('23:59');
    assert.ok(Number.isInteger(t) && t > 0);
    assert.match(L.fmtUnix(t), /23:59/);
    assert.equal(L.parseStart('2030-01-02T03:04:05Z'), Math.floor(Date.parse('2030-01-02T03:04:05Z') / 1000));
    assert.throws(() => L.parseStart('not-a-time'), /bad --start/);
  });

  it('classify maps reverts to wait / fatal / unknown, with overrides', () => {
    assert.equal(L.classify('NotStarted'), 'wait');
    assert.equal(L.classify('TooEarly'), 'wait');
    assert.equal(L.classify('SoldOut'), 'fatal');
    assert.equal(L.classify('AlreadyClaimed'), 'fatal');
    assert.equal(L.classify('AgentIdRequired'), 'fatal');
    assert.equal(L.classify('ZebraUnicorn'), 'unknown');
    assert.equal(L.classify('SoldOut', { waitRe: /sold/i }), 'wait');
    assert.equal(L.classify('NotStarted', { fatalRe: /notstarted/i }), 'fatal');
  });

  it('isRevert / hasRevertData distinguish reverts from transport errors', () => {
    const withData = { rpcError: { data: '0x08c379a0', message: 'execution reverted' } };
    assert.equal(L.isRevert(withData), true);
    assert.equal(L.hasRevertData(withData), true);
    const noData = { rpcError: { message: 'execution reverted: boom' } };
    assert.equal(L.isRevert(noData), true);
    assert.equal(L.hasRevertData(noData), false);
    assert.equal(L.isRevert({ message: 'socket hang up' }), false);
    assert.equal(L.isRevert({ rpcError: { message: 'rate limit' } }), false);
  });

  it('decodeRevert decodes a known custom error and Error(string) offline', async () => {
    // ethers v6 Interface has no encodeError(); build revert data by hand:
    // 4-byte selector + ABI-encoded args.
    const notStartedData = ethers.id('NotStarted()').slice(0, 10);
    const errData = ethers.id('Error(string)').slice(0, 10)
      + ethers.AbiCoder.defaultAbiCoder().encode(['string'], ['boom']).slice(2);
    const d1 = await L.decodeRevert({ rpcError: { data: notStartedData, message: 'execution reverted' } }, null);
    assert.equal(d1.name, 'NotStarted');
    const d2 = await L.decodeRevert({ rpcError: { data: errData, message: 'execution reverted' } }, null);
    assert.equal(d2.name, 'boom');
    assert.equal(d2.isString, true);
    const d3 = await L.decodeRevert({ rpcError: { message: 'execution reverted: CustomThing' } }, null);
    assert.equal(d3.name, 'CustomThing');
  });

  it('hostOf returns only the host (keys never leak into logs)', () => {
    assert.equal(L.hostOf('https://user:key@quiknode.example/v2/abc123'), 'quiknode.example');
    assert.equal(L.hostOf('https://bsc-rpc.publicnode.com'), 'bsc-rpc.publicnode.com');
  });
});

// ---------- fire.js value guards (die before any network/baw use) ----------
describe('fire.js value guards', () => {
  it('value > 0 without --maxValue is refused', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--value', '0.01', '--dry']);
      assert.equal(r.status, 2);
      assert.match(r.stdout, /requires --maxValue/);
      assert.doesNotMatch(r.stdout + r.stderr, /ReferenceError/); // TDZ regression (fixed 2026-11-17)
    } finally { cleanup(wd); }
  });

  it('value > maxValue is refused', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--value', '0.02', '--maxValue', '0.01', '--dry']);
      assert.equal(r.status, 2);
      assert.match(r.stdout, /value 0\.02 BNB > maxValue 0\.01 BNB/);
      assert.doesNotMatch(r.stdout + r.stderr, /ReferenceError/); // TDZ regression (fixed 2026-11-17)
    } finally { cleanup(wd); }
  });

  it('value == maxValue passes the guard (dry run reaches the DRY stop)', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--value', '0.01', '--maxValue', '0.01', '--dry', '--noWs', '--once', '--allowUnverified']);
      assert.equal(r.status, 0, r.stdout + r.stderr);
      assert.match(r.stdout, /DRY: stop before execute/);
    } finally { cleanup(wd); }
  });
});

// ---------- fire.js lock file ----------
describe('fire.js one-broadcast lock', () => {
  it('second run with the same call refuses (lock exists)', async () => {
    const wd = makeWorkdir();
    try {
      const args = ['--to', TO, '--data', DATA, '--noWs', '--once', '--allowUnverified'];
      const r1 = await runFire(wd, args);
      assert.equal(r1.status, 0, r1.stdout + r1.stderr);
      assert.match(r1.stdout, /RECEIPT SUCCESS/);
      const locks = fs.readdirSync(path.join(wd.dir, 'runs')).filter(f => f.startsWith('lock_'));
      assert.equal(locks.length, 1, 'exactly one lock file after the first broadcast');
      const executes = r1.stubCalls.filter(c => c.argv[1] === 'execute');
      assert.equal(executes.length, 1, 'exactly one execute call');
      const r2 = await runFire(wd, args);
      assert.equal(r2.status, 1);
      assert.match(r2.stdout, /lock exists/);
    } finally { cleanup(wd); }
  });
});

// ---------- fire.js --expectNft ----------
describe('fire.js --expectNft', () => {
  it('executes (dry) when exactly n NFTs arrive', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--noWs', '--once', '--expectNft', '2', '--allowUnverified'], { STUB_NFTS: '2' });
      assert.equal(r.status, 0, r.stdout + r.stderr);
      assert.match(r.stdout, /DRY: stop before execute/);
    } finally { cleanup(wd); }
  });

  it('refuses when fewer NFTs arrive than expected', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--noWs', '--once', '--expectNft', '2', '--allowUnverified'], { STUB_NFTS: '1' });
      assert.equal(r.status, 1);
      assert.match(r.stdout, /preview shows 1 NFT\(s\) arriving, expected 2/);
    } finally { cleanup(wd); }
  });
});

// ---------- fire.js dynamic args ----------
describe('fire.js dynamic args', () => {
  const dryArgs = (sig, argsJson) => ['--to', TO, '--sig', sig, '--args', argsJson, '--dry', '--noWs', '--once', '--allowUnverified'];

  it('$agentId resolves to uint256(keccak256(handle))', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, dryArgs('mintFree(uint256)', '["$agentId"]'));
      assert.equal(r.status, 0, r.stdout + r.stderr);
      const iface = new ethers.Interface(['function mintFree(uint256)']);
      const [v] = iface.decodeFunctionData('mintFree', previewInputData(r));
      assert.equal(v, BigInt(ethers.id('alice')));
    } finally { cleanup(wd); }
  });

  it('$now+1800 resolves to now + 1800 seconds', async () => {
    const wd = makeWorkdir();
    try {
      const before = Math.floor(Date.now() / 1000);
      const r = await runFire(wd, dryArgs('mint(uint256)', '["$now+1800"]'));
      const after = Math.floor(Date.now() / 1000);
      assert.equal(r.status, 0, r.stdout + r.stderr);
      const iface = new ethers.Interface(['function mint(uint256)']);
      const [v] = iface.decodeFunctionData('mint', previewInputData(r));
      assert.ok(v >= BigInt(before + 1800) && v <= BigInt(after + 1800), `got ${v}`);
    } finally { cleanup(wd); }
  });

  it('{"getter":"totalMinted()","add":1} re-reads the getter (41 + 1 = 42)', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, dryArgs('mint(uint256)', '[{"getter":"totalMinted()","add":1}]'));
      assert.equal(r.status, 0, r.stdout + r.stderr);
      const iface = new ethers.Interface(['function mint(uint256)']);
      const [v] = iface.decodeFunctionData('mint', previewInputData(r));
      assert.equal(v, 42n);
    } finally { cleanup(wd); }
  });

  it('$wallet resolves to the connected wallet address', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, dryArgs('mint(address)', '["$wallet"]'));
      assert.equal(r.status, 0, r.stdout + r.stderr);
      const iface = new ethers.Interface(['function mint(address)']);
      const [v] = iface.decodeFunctionData('mint', previewInputData(r));
      assert.equal(String(v).toLowerCase(), WALLET.toLowerCase());
    } finally { cleanup(wd); }
  });

  it('unknown dynamic arg fails instead of firing', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, dryArgs('mint(uint256)', '["$bogus"]'));
      assert.equal(r.status, 1);
      assert.match(r.stdout, /unknown dynamic arg \$bogus/);
    } finally { cleanup(wd); }
  });
});

// ---------- fire.js --allowUnverified (brief item 15) ----------
// The stub contract 0x2222... has no Sourcify ABI, so it is unverified.
describe('fire.js --allowUnverified (brief item 15)', () => {
  it('refuses an unverified contract without --allowUnverified', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--noWs', '--once']);
      assert.equal(r.status, 1);
      assert.match(r.stdout, /UNVERIFIED/);
      assert.match(r.stdout, /--allowUnverified/);
      assert.match(r.stdout, /lanjut tanpa verifikasi/);
      assert.equal(r.stubCalls.filter(c => c.argv[1] === 'execute').length, 0, 'no execute on refusal');
    } finally { cleanup(wd); }
  });

  it('proceeds (dry) with --allowUnverified and logs the override', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--noWs', '--once', '--allowUnverified']);
      assert.equal(r.status, 0, r.stdout + r.stderr);
      assert.match(r.stdout, /DRY: stop before execute/);
      assert.match(r.stdout, /WARN UNVERIFIED contract/);
    } finally { cleanup(wd); }
  });

  it('unknown flag --allowUnverifiedTypo still fails (no silent pass-through)', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--allowUnverifiedTypo']);
      assert.equal(r.status, 2);
      assert.match(r.stdout + r.stderr, /unknown arg/);
    } finally { cleanup(wd); }
  });
});

// ---------- fire.js --expectNft warning (brief item 17a) ----------
describe('fire.js --expectNft warning (brief item 17a)', () => {
  it('warns "tidak ada verifikasi hasil" when --expectNft is not set', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--noWs', '--once', '--allowUnverified']);
      assert.equal(r.status, 0, r.stdout + r.stderr);
      assert.match(r.stdout, /tidak ada verifikasi hasil/);
    } finally { cleanup(wd); }
  });

  it('does not warn when --expectNft is set and satisfied', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--noWs', '--once', '--expectNft', '2', '--allowUnverified'], { STUB_NFTS: '2' });
      assert.equal(r.status, 0, r.stdout + r.stderr);
      assert.doesNotMatch(r.stdout, /tidak ada verifikasi hasil/);
    } finally { cleanup(wd); }
  });
});

// ---------- fire.js gas cap ~400000 (brief item 17b) ----------
describe('fire.js gas cap ~400000 (brief item 17b)', () => {
  it('--gasLimit above 400000 is refused at startup', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--gasLimit', '500000']);
      assert.equal(r.status, 2);
      assert.match(r.stdout, /400000/);
    } finally { cleanup(wd); }
  });

  it('a preview estimating 500000 gas refuses (dry)', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--noWs', '--once', '--allowUnverified'], { STUB_GAS: '500000' });
      assert.equal(r.status, 1);
      assert.match(r.stdout, /gas estimate 500000 > ~400000/);
    } finally { cleanup(wd); }
  });

  it('a preview estimating 200000 gas proceeds (dry)', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runFire(wd, ['--to', TO, '--data', DATA, '--dry', '--noWs', '--once', '--allowUnverified'], { STUB_GAS: '200000' });
      assert.equal(r.status, 0, r.stdout + r.stderr);
      assert.match(r.stdout, /DRY: stop before execute/);
    } finally { cleanup(wd); }
  });
});

// ---------- fire.js two parallel processes (brief item 17c) ----------
describe('fire.js one-broadcast lock under parallel runs (brief item 17c)', () => {
  it('two processes racing the same call execute exactly once', async () => {
    const wd = makeWorkdir();
    try {
      const args = ['--to', TO, '--data', DATA, '--noWs', '--once', '--allowUnverified'];
      const [r1, r2] = await Promise.all([runFire(wd, args), runFire(wd, args)]);
      const statuses = [r1.status, r2.status].sort();
      assert.deepEqual(statuses, [0, 1], `expected one success + one refusal, got ${r1.status}/${r2.status}:\n${r1.stdout}\n---\n${r2.stdout}`);
      const loser = r1.status === 1 ? r1 : r2;
      assert.match(loser.stdout, /lock (exists|appeared)/);
      // Both runs share one stub log: exactly one execute across both.
      const executes = r1.stubCalls.filter(c => c.argv[1] === 'execute');
      assert.equal(executes.length, 1, 'exactly one execute call across both processes');
      const locks = fs.readdirSync(path.join(wd.dir, 'runs')).filter(f => f.startsWith('lock_'));
      assert.equal(locks.length, 1, 'exactly one lock file after the race');
    } finally { cleanup(wd); }
  });
});

// ---------- recon.js unverified flag + pre-open gates (brief items 15 + 16) ----------
describe('recon.js unverified flag + pre-open gates (brief items 15 + 16)', () => {
  it('flags an unverified contract red and reports the pre-open GATE line + JSON', async () => {
    const wd = makeWorkdir();
    try {
      const r = await runRecon(wd, ['--contract', TO, '--json']);
      assert.equal(r.status, 0, r.stdout + r.stderr);
      assert.match(r.stdout, /UNVERIFIED CONTRACT/);
      assert.match(r.stdout, /--allowUnverified/);
      assert.match(r.stdout, /GATE pre-open: verified=NO/);
      assert.match(r.stdout, /preview gate NOT checkable pre-open/);
      const files = fs.readdirSync(path.join(wd.dir, 'runs')).filter(f => f.startsWith('recon_') && f.endsWith('.json'));
      assert.equal(files.length, 1, 'one recon JSON written');
      const out = JSON.parse(fs.readFileSync(path.join(wd.dir, 'runs', files[0]), 'utf8'));
      assert.equal(out.contracts.length, 1);
      assert.equal(out.contracts[0].verified, false);
      assert.equal(out.contracts[0].gate.verified, false);
      assert.equal(out.contracts[0].gate.sim, 'no-abi');
      assert.match(out.warnings.join(' '), /UNVERIFIED contract/);
    } finally { cleanup(wd); }
  });
});
