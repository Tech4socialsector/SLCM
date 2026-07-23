#!/bin/bash
# ============================================================
# NLSAT Merit System — Full Test Runner
# Runs all 69 tests across merit_system test folder
# Usage: bash run_merit_tests.sh
# ============================================================

set -e

BENCH_DIR="/home/bsoft/frappe-bench"
PYTHON="$BENCH_DIR/env/bin/python"
TEST_DIR="$BENCH_DIR/apps/slcm/slcm/tests/merit_system"

echo ""
echo "============================================================"
echo "  NLSAT Merit System — Full Test Suite (69 tests)"
echo "============================================================"
echo ""

PYTEST_PASS=0
PYTEST_FAIL=0
BENCH_PASS=0
BENCH_FAIL=0

# --- PART 1: pytest-based tests (38 tests) ---
echo ">>> [1/2] Running pytest-based tests (38 tests)..."
echo ""

cd "$TEST_DIR"
if $PYTHON -m pytest . -v --ignore=test_advanced_merit_scenarios.py --tb=short 2>&1; then
    PYTEST_PASS=38
    PYTEST_FAIL=0
    echo ""
    echo "✅ pytest tests: PASSED"
else
    PYTEST_FAIL=1
    echo ""
    echo "❌ pytest tests: SOME FAILURES (see above)"
fi

# --- PART 2: bench integration tests (31 tests) ---
echo ""
echo ">>> [2/2] Running bench integration tests (31 tests, ~7 min)..."
echo ""

cd "$BENCH_DIR"
if bench --site slcm.com run-tests --app slcm \
    --module slcm.tests.merit_system.test_advanced_merit_scenarios 2>&1; then
    BENCH_PASS=31
    BENCH_FAIL=0
    echo ""
    echo "✅ Integration tests: PASSED"
else
    BENCH_FAIL=1
    echo ""
    echo "❌ Integration tests: SOME FAILURES (see above)"
fi

# --- SUMMARY ---
echo ""
echo "============================================================"
echo "  FINAL SUMMARY"
echo "============================================================"
echo "  pytest tests  : 38 tests"
echo "  bench tests   : 31 tests"
echo "  Total         : 69 tests"
echo ""
if [ $PYTEST_FAIL -eq 0 ] && [ $BENCH_FAIL -eq 0 ]; then
    echo "  🎉 ALL TESTS PASSED!"
else
    echo "  ⚠️  SOME TESTS FAILED — check output above"
    exit 1
fi
echo "============================================================"
echo ""
