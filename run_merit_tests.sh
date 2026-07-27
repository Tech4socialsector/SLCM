#!/bin/bash
# ============================================================
# NLSAT Merit System — Full Test Runner
# Runs all tests using bench run-tests (no pytest needed)
# Usage: bash run_merit_tests.sh
# ============================================================

BENCH_DIR="/home/bsoft/frappe-bench"

echo ""
echo "============================================================"
echo "  NLSAT Merit System — Full Test Suite"
echo "============================================================"
echo ""

PASS=0
FAIL=0

# --- PART 1: Unit/mock-based tests (36 tests) ---
echo ">>> [1/2] Running unit tests (36 tests, ~2 min)..."
echo ""

cd "$BENCH_DIR"
if bench --site slcm.com run-tests --app slcm \
    --module slcm.tests.merit_system.test_merit_system_bench 2>&1; then
    PASS=$((PASS + 1))
    echo ""
    echo "✅ Unit tests: PASSED"
else
    FAIL=$((FAIL + 1))
    echo ""
    echo "❌ Unit tests: SOME FAILURES"
fi

# --- PART 2: Marks import/export integration tests (3 tests) ---
echo ""
echo ">>> [2/3] Running marks import/export tests (3 tests)..."
echo ""

if bench --site slcm.com run-tests --app slcm \
    --module slcm.tests.merit_system.test_marks_import_export 2>&1; then
    PASS=$((PASS + 1))
    echo ""
    echo "✅ Marks import/export tests: PASSED"
else
    FAIL=$((FAIL + 1))
    echo ""
    echo "❌ Marks import/export tests: SOME FAILURES"
fi

# --- PART 3: Advanced edge case tests (31 tests, real dataset) ---
echo ""
echo ">>> [3/3] Running advanced edge case tests (31 tests, ~7 min)..."
echo ""

if bench --site slcm.com run-tests --app slcm \
    --module slcm.tests.merit_system.test_advanced_merit_scenarios 2>&1; then
    PASS=$((PASS + 1))
    echo ""
    echo "✅ Advanced edge case tests: PASSED"
else
    FAIL=$((FAIL + 1))
    echo ""
    echo "❌ Advanced edge case tests: SOME FAILURES"
fi

# --- SUMMARY ---
echo ""
echo "============================================================"
echo "  FINAL SUMMARY"
echo "============================================================"
echo "  Test Groups Passed : $PASS / 3"
echo "  Test Groups Failed : $FAIL / 3"
echo ""
if [ $FAIL -eq 0 ]; then
    echo "  🎉 ALL TESTS PASSED!"
else
    echo "  ⚠️  SOME TESTS FAILED — check output above"
    exit 1
fi
echo "============================================================"
echo ""
