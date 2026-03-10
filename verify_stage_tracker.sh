#!/bin/bash
# =============================================================
# Application Stage Tracker — Gap Verification Script
# Run from: /home/joy-sathish/frappe/slcm/apps/slcm
# Usage: bash verify_stage_tracker.sh
# =============================================================

BENCH_DIR="/home/joy-sathish/frappe/slcm"
APP_DIR="$BENCH_DIR/apps/slcm/slcm"
SITE="slcm.com"
PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}PASS${NC}  $1"; ((PASS++)); }
fail() { echo -e "${RED}FAIL${NC}  $1"; ((FAIL++)); }
header() { echo -e "\n${YELLOW}=== $1 ===${NC}"; }

# =============================================================
header "1. FILE EXISTENCE"
# =============================================================

FILES=(
  "admission/doctype/application_stage_tracker/__init__.py"
  "admission/doctype/application_stage_tracker/application_stage_tracker.json"
  "admission/doctype/application_stage_tracker/application_stage_tracker.py"
  "admission/doctype/application_stage_log/__init__.py"
  "admission/doctype/application_stage_log/application_stage_log.json"
  "admission/doctype/application_stage_log/application_stage_log.py"
  "admission/doctype/stage_status_map/__init__.py"
  "admission/doctype/stage_status_map/stage_status_map.json"
  "admission/doctype/stage_status_map/stage_status_map.py"
  "admission/utils/stage_tracker.py"
  "fixtures/stage_status_map.json"
)

for f in "${FILES[@]}"; do
  if [ -f "$APP_DIR/$f" ]; then pass "$f"; else fail "$f — MISSING"; fi
done

# =============================================================
header "2. stage_tracker.py — FUNCTION DEFINITIONS"
# =============================================================

ST="$APP_DIR/admission/utils/stage_tracker.py"
if [ -f "$ST" ]; then
  for fn in "def get_stage_mapping" "def resolve_stage" "def calculate_progress" \
            "def sync_tracker" "def sync_tracker_hook" "def admin_override"; do
    grep -q "$fn" "$ST" && pass "stage_tracker: $fn" || fail "stage_tracker: $fn — MISSING"
  done
else
  fail "stage_tracker.py does not exist — skipping function checks"
fi

# =============================================================
header "3. application_stage_tracker.py — CONTROLLER CHECKS"
# =============================================================

AST="$APP_DIR/admission/doctype/application_stage_tracker/application_stage_tracker.py"
if [ -f "$AST" ]; then
  grep -q "class ApplicationStageTracker" "$AST" && pass "class ApplicationStageTracker defined" || fail "class ApplicationStageTracker — MISSING"
  grep -q "def before_save"               "$AST" && pass "before_save defined"                    || fail "before_save — MISSING"
  grep -q "def validate"                  "$AST" && pass "validate defined"                        || fail "validate — MISSING"
  grep -q "immutable\|is_new"             "$AST" && pass "immutability guard present"              || fail "immutability guard — MISSING"
else
  fail "application_stage_tracker.py does not exist"
fi

# =============================================================
header "4. applicant.py — HOOK INTEGRATION"
# =============================================================

AP="$APP_DIR/admission/doctype/applicant/applicant.py"
if [ -f "$AP" ]; then
  grep -q "sync_tracker"                  "$AP" && pass "sync_tracker imported/called"           || fail "sync_tracker — NOT CALLED in applicant.py"
  grep -q "def on_update"                 "$AP" && pass "on_update method present"               || fail "on_update — MISSING in applicant.py"
  grep -q "has_value_changed.*application_status\|application_status.*has_value_changed" "$AP" \
    && pass "has_value_changed check present" || fail "has_value_changed check — MISSING"
  grep -q "frappe.log_error\|log_error"   "$AP" && pass "error handling with log_error"         || fail "log_error — MISSING (no error guard)"
else
  fail "applicant.py not found"
fi

# =============================================================
header "5. hooks.py — DOC_EVENTS + FIXTURES"
# =============================================================

HOOKS="$APP_DIR/../hooks.py"
# Try alternate location
[ ! -f "$HOOKS" ] && HOOKS="$BENCH_DIR/apps/slcm/hooks.py"
[ ! -f "$HOOKS" ] && HOOKS=$(find "$BENCH_DIR/apps/slcm" -maxdepth 2 -name "hooks.py" | head -1)

if [ -f "$HOOKS" ]; then
  grep -q "sync_tracker_hook\|Application Stage Tracker" "$HOOKS" \
    && pass "hooks.py: doc_events Applicant → sync_tracker_hook"  \
    || fail "hooks.py: doc_events entry MISSING"
  grep -q "Stage Status Map" "$HOOKS" \
    && pass "hooks.py: fixtures includes Stage Status Map"         \
    || fail "hooks.py: fixtures missing Stage Status Map"
  grep -q "doc_events" "$HOOKS" \
    && pass "hooks.py: doc_events dict exists"                     \
    || fail "hooks.py: doc_events dict NOT FOUND"
  grep -q "fixtures" "$HOOKS" \
    && pass "hooks.py: fixtures list exists"                       \
    || fail "hooks.py: fixtures list NOT FOUND"
else
  fail "hooks.py not found — searched multiple locations"
fi

# =============================================================
header "6. web.py — get_stage_tracker_data UPDATE"
# =============================================================

WEB="$APP_DIR/admission/utils/web.py"
if [ -f "$WEB" ]; then
  grep -q "def get_stage_tracker_data"                                   "$WEB" && pass "get_stage_tracker_data function present"          || fail "get_stage_tracker_data — MISSING"
  grep -q "from slcm.admission.utils.stage_tracker import get_stage_mapping" "$WEB" && pass "get_stage_mapping imported in web.py"        || fail "get_stage_mapping import — MISSING"
  grep -q "Application Stage Tracker"                                    "$WEB" && pass "Application Stage Tracker queried"               || fail "Application Stage Tracker query — MISSING"
  grep -q "show_action"                                                  "$WEB" && pass "show_action field in output"                      || fail "show_action — MISSING"
  grep -q "Fallback\|fallback"                                           "$WEB" && pass "fallback logic present (no tracker case)"        || fail "fallback logic — MISSING"
  grep -q "is_terminal"                                                  "$WEB" && pass "is_terminal in output"                           || fail "is_terminal — MISSING"
else
  fail "web.py not found"
fi

# =============================================================
header "7. JSON STRUCTURE — DocType fields spot-check"
# =============================================================

AST_JSON="$APP_DIR/admission/doctype/application_stage_tracker/application_stage_tracker.json"
if [ -f "$AST_JSON" ]; then
  for field in "applicant" "admission_year" "admission_cycle" "intake_type" \
               "current_status" "current_stage" "stage_progress_pct"        \
               "is_terminal" "last_transition_on" "last_updated_by"         \
               "override_note" "log"; do
    grep -q "\"$field\"" "$AST_JSON" && pass "AST JSON: field '$field'" || fail "AST JSON: field '$field' — MISSING"
  done
else
  fail "application_stage_tracker.json not found"
fi

LOG_JSON="$APP_DIR/admission/doctype/application_stage_log/application_stage_log.json"
if [ -f "$LOG_JSON" ]; then
  grep -q '"istable": 1\|"istable":1' "$LOG_JSON" && pass "application_stage_log: istable=1" || fail "application_stage_log: istable NOT SET — will break child table"
  for field in "from_status" "to_status" "from_stage" "to_stage" "stage_state" \
               "transition_date" "triggered_by" "performed_by" "remarks"; do
    grep -q "\"$field\"" "$LOG_JSON" && pass "Log JSON: field '$field'" || fail "Log JSON: field '$field' — MISSING"
  done
else
  fail "application_stage_log.json not found"
fi

SSM_JSON="$APP_DIR/admission/doctype/stage_status_map/stage_status_map.json"
if [ -f "$SSM_JSON" ]; then
  for field in "intake_type" "application_status" "stage_type" "stage_state" "sequence" "is_terminal" "is_active"; do
    grep -q "\"$field\"" "$SSM_JSON" && pass "SSM JSON: field '$field'" || fail "SSM JSON: field '$field' — MISSING"
  done
else
  fail "stage_status_map.json not found"
fi

# =============================================================
header "8. FIXTURE FILE — row count and intake coverage"
# =============================================================

FIX="$APP_DIR/fixtures/stage_status_map.json"
if [ -f "$FIX" ]; then
  CLAT_ROWS=$(grep -c '"CLAT"'  "$FIX")
  NLSAT_ROWS=$(grep -c '"NLSAT"' "$FIX")
  TOTAL_ROWS=$(grep -c '"Stage Status Map"' "$FIX")
  echo "  INFO  Fixture rows: CLAT=$CLAT_ROWS  NLSAT=$NLSAT_ROWS  Total=$TOTAL_ROWS"
  [ "$CLAT_ROWS"  -ge 9 ] && pass "CLAT rows >= 9"  || fail "CLAT rows < 9 (expected 9, got $CLAT_ROWS)"
  [ "$NLSAT_ROWS" -ge 13 ] && pass "NLSAT rows >= 13" || fail "NLSAT rows < 13 (expected 13, got $NLSAT_ROWS)"
  grep -q '"is_terminal": 1\|"is_terminal":1' "$FIX" && pass "Terminal rows present (Rejected/Waitlisted)" || fail "No terminal rows found"
else
  fail "stage_status_map.json fixture not found"
fi

# =============================================================
header "9. DATABASE — DocType registration + fixture rows"
# =============================================================

cd "$BENCH_DIR" || exit 1

echo "  Checking tabDocType..."
bench --site $SITE mariadb --execute \
  "SELECT name, module FROM \`tabDocType\` WHERE name IN ('Application Stage Tracker','Application Stage Log','Stage Status Map');" \
  2>/dev/null | grep -E "Application|Stage" \
  && pass "DocTypes registered in database" \
  || fail "DocTypes NOT in tabDocType — run: bench --site $SITE migrate"

echo ""
echo "  Checking tabStage Status Map row count..."
ROW_COUNT=$(bench --site $SITE mariadb --execute \
  "SELECT COUNT(*) as cnt FROM \`tabStage Status Map\`;" 2>/dev/null | grep -E '[0-9]+' | tail -1 | tr -d ' ')
if [ -n "$ROW_COUNT" ] && [ "$ROW_COUNT" -ge 22 ]; then
  pass "Stage Status Map: $ROW_COUNT rows loaded (expected >= 22)"
elif [ -n "$ROW_COUNT" ]; then
  fail "Stage Status Map: only $ROW_COUNT rows — expected >= 22. Run: bench --site $SITE import-fixtures --app slcm"
else
  fail "Stage Status Map table empty or not found — run migrate + import-fixtures"
fi

echo ""
echo "  Checking tabApplication Stage Tracker exists..."
bench --site $SITE mariadb --execute \
  "SELECT COUNT(*) FROM \`tabApplication Stage Tracker\` LIMIT 1;" 2>/dev/null \
  && pass "tabApplication Stage Tracker table exists" \
  || fail "tabApplication Stage Tracker table MISSING — run migrate"

echo ""
echo "  Checking Admission Cycle Stage has stage_type field..."
bench --site $SITE mariadb --execute \
  "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='tabAdmission Cycle Stage' AND COLUMN_NAME='stage_type';" \
  2>/dev/null | grep -q "stage_type" \
  && pass "Admission Cycle Stage: stage_type column exists" \
  || fail "Admission Cycle Stage: stage_type column MISSING — stage resolution will fail"

# =============================================================
header "10. IMPORT + SYNTAX CHECK"
# =============================================================

echo "  Python syntax check on stage_tracker.py..."
python3 -c "
import ast, sys
try:
    with open('$APP_DIR/admission/utils/stage_tracker.py') as f:
        ast.parse(f.read())
    print('SYNTAX OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
    sys.exit(1)
" && pass "stage_tracker.py syntax valid" || fail "stage_tracker.py has syntax errors"

echo "  Python syntax check on applicant.py..."
python3 -c "
import ast, sys
try:
    with open('$APP_DIR/admission/doctype/applicant/applicant.py') as f:
        ast.parse(f.read())
    print('SYNTAX OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
    sys.exit(1)
" && pass "applicant.py syntax valid" || fail "applicant.py has syntax errors"

echo "  Python syntax check on web.py..."
python3 -c "
import ast, sys
try:
    with open('$APP_DIR/admission/utils/web.py') as f:
        ast.parse(f.read())
    print('SYNTAX OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
    sys.exit(1)
" && pass "web.py syntax valid" || fail "web.py has syntax errors"

# =============================================================
header "11. LIVE FUNCTION TEST (bench execute)"
# =============================================================

echo "  Testing get_stage_mapping for CLAT..."
bench --site $SITE execute slcm.admission.utils.stage_tracker.get_stage_mapping \
  --args '["CLAT"]' 2>/dev/null | grep -q "Application\|stage_type" \
  && pass "get_stage_mapping(CLAT) returns data" \
  || fail "get_stage_mapping(CLAT) returned empty — fixture rows missing or import failed"

echo "  Testing get_stage_mapping for NLSAT..."
bench --site $SITE execute slcm.admission.utils.stage_tracker.get_stage_mapping \
  --args '["NLSAT"]' 2>/dev/null | grep -q "Entrance Test\|Interview\|stage_type" \
  && pass "get_stage_mapping(NLSAT) returns data" \
  || fail "get_stage_mapping(NLSAT) returned empty"

# =============================================================
header "SUMMARY"
# =============================================================

TOTAL=$((PASS + FAIL))
echo ""
echo "  Total checks : $TOTAL"
echo -e "  ${GREEN}Passed${NC}       : $PASS"
echo -e "  ${RED}Failed${NC}       : $FAIL"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}ALL CHECKS PASSED ✓${NC}"
  echo "Safe to run: bench --site $SITE migrate && bench --site $SITE import-fixtures --app slcm"
else
  echo -e "${RED}$FAIL GAP(S) FOUND — fix above failures before running migrate${NC}"
  echo ""
  echo "Quick fix commands:"
  echo "  bench --site $SITE migrate                          # register DocTypes"
  echo "  bench --site $SITE import-fixtures --app slcm       # load Stage Status Map rows"
  echo "  bench --site $SITE clear-cache && bench restart     # clear cache"
fi
