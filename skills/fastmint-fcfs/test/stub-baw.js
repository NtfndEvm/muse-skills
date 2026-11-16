#!/usr/bin/env node
// Stub `baw` for the offline tests in fastmint.test.js. NOT a real wallet:
// it only answers the fixed calls fire.js makes (status / address /
// settings / contract-call preview / contract-call execute) with canned
// success JSON. Never put this on PATH outside the tests.
//
// Env:
//   STUB_WALLET  wallet address returned by `wallet address`
//   STUB_NFTS    how many ERC721 balance-change entries the preview shows
//                arriving in the wallet (default 0)
//   STUB_GAS     gas estimate (estimatedGas) the preview reports (default: none)
//   STUB_LOG     file to append one JSON line per invocation to
'use strict';
const fs = require('fs');

const WALLET = process.env.STUB_WALLET || '0x1111111111111111111111111111111111111111';
const argv = process.argv.slice(2);

try {
  if (process.env.STUB_LOG) fs.appendFileSync(process.env.STUB_LOG, JSON.stringify({ argv }) + '\n');
} catch {}

const flag = name => {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : null;
};
const out = obj => { console.log(JSON.stringify(obj)); };

if (argv[0] === 'wallet' && argv[1] === 'status') {
  out({ success: true, data: { status: 'CONNECTED' } });
} else if (argv[0] === 'wallet' && argv[1] === 'address') {
  out({ success: true, data: { addresses: [{ binanceChainId: '56', address: WALLET }] } });
} else if (argv[0] === 'wallet' && argv[1] === 'settings') {
  out({
    success: true,
    data: {
      devMode: { enabled: true, expiresAt: '2999-01-01T00:00:00.000Z', dailyLimit: 100 },
      developerModeQuotaUsed: 0,
      sessionExpireTime: '2999-01-01T00:00:00.000Z',
    },
  });
} else if (argv[0] === 'contract-call' && argv[1] === 'preview') {
  const n = parseInt(process.env.STUB_NFTS || '0', 10);
  const to = flag('--to');
  const from = flag('--from');
  const balanceChanges = [];
  for (let i = 0; i < n; i++) {
    balanceChanges.push({ tokenType: 'ERC721', owner: from, contractAddress: to, change: '1' });
  }
  const sim = { simulationCode: '000000000', balanceChanges };
  if (process.env.STUB_GAS) sim.estimatedGas = Number(process.env.STUB_GAS);
  out({
    success: true,
    data: {
      requestId: 'req-test-1',
      requireConfirmation: false,
      simulationResult: sim,
      risks: {},
    },
  });
} else if (argv[0] === 'contract-call' && argv[1] === 'execute') {
  out({
    success: true,
    data: { status: 'SUCCESS', orderId: 'ord-test', txHash: '0x' + 'ab'.repeat(32) },
  });
} else {
  out({ success: false, error: { code: 1, message: 'stub-baw: unknown command ' + argv.join(' ') } });
}
