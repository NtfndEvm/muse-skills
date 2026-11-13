"""Tests for scripts/token_scanner.py (EVM-only adaptation).

Stdlib only. Run: python3 -m unittest discover -s scripts -p "test_*.py" -v
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCANNER = HERE / "token_scanner.py"

sys.path.insert(0, str(HERE))
from token_scanner import TokenScanner, RiskLevel  # noqa: E402

RUGGY = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract RugToken {
    mapping(address => uint256) public _balances;
    mapping(address => bool) public _isBlacklisted;
    uint256 public _totalSupply;
    uint256 public _sellFee;
    address public owner;

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }

    function _mint(address to, uint256 amount) internal {
        _balances[to] += amount;
        _totalSupply += amount;
    }

    function blacklist(address a) external {
        _isBlacklisted[a] = true;
    }

    function setSellFee(uint256 fee) external {
        _sellFee = fee;
    }

    function renounceOwnership() public override {
        // does nothing: fake renounce
    }
}
"""

CLEAN = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract CleanToken is ERC20 {
    uint256 public constant MAX_SUPPLY = 1_000_000 ether;

    constructor() ERC20("Clean", "CLN") {
        _mint(msg.sender, 100_000 ether);
    }
}
"""


def _write(tmpdir, name, content):
    p = Path(tmpdir) / name
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestScanner(unittest.TestCase):
    def test_ruggy_contract_flags_critical_and_high(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write(d, "RugToken.sol", RUGGY)
            result = TokenScanner(path).scan()
            titles = {f.title for f in result.findings}
            self.assertIn("Public mint function", titles)
            self.assertIn("Blacklist mapping", titles)
            self.assertIn("Blacklist setter function", titles)
            self.assertIn("Fee setter function", titles)
            self.assertIn("renounceOwnership override", titles)
            self.assertTrue(
                any(f.risk is RiskLevel.CRITICAL for f in result.findings),
                "expected at least one CRITICAL finding",
            )
            self.assertGreaterEqual(result.risk_score, 50)

    def test_clean_contract_has_no_critical_or_high(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write(d, "CleanToken.sol", CLEAN)
            result = TokenScanner(path).scan()
            bad = [f for f in result.findings if f.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH)]
            self.assertEqual(bad, [], f"unexpected findings: {[f.title for f in bad]}")

    def test_cli_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            ruggy = _write(d, "RugToken.sol", RUGGY)
            clean = _write(d, "CleanToken.sol", CLEAN)
            r1 = subprocess.run(
                [sys.executable, str(SCANNER), ruggy, "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(r1.returncode, 1, "ruggy contract must exit 1")
            r2 = subprocess.run(
                [sys.executable, str(SCANNER), clean, "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(r2.returncode, 0, "clean contract must exit 0")


if __name__ == "__main__":
    unittest.main()
