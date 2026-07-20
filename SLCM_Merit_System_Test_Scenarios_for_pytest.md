# NLSAT SLCM Merit-Ranking & Seat Allocation System — Comprehensive pytest Test Scenarios

**Objective:** Complete test coverage for multi-stage merit ranking, reservation policy enforcement, tiebreak logic, and seat allocation. Designed for senior-level testing rigor.

---

## TEST ORGANIZATION STRUCTURE

```
tests/
├── test_shortlisting_merit.py          # Stage 1: Part A ranking and 1:5 shortlist
├── test_final_merit_ranking.py          # Stage 2: Part A+B ranking with tiebreaks
├── test_seat_allocation.py              # Stage 3: 120-seat allocation with reservation
├── test_reservation_policy.py           # Vertical, compartmentalized, overall logic
├── test_tiebreak_logic.py               # DOB, Applicant ID, Part B tiebreaks
├── test_boundary_conditions.py          # Cutoff edges, tied groups, overflows
├── test_data_consistency.py             # Cross-stage validation, data integrity
├── test_error_handling.py               # Invalid data, missing fields, malformed records
├── test_performance_load.py             # Stress tests with 2500+ candidates
└── fixtures/
    ├── candidate_fixtures.py            # Reusable test candidate data
    ├── score_generators.py              # Synthetic score/DOB generation
    └── test_data.py                     # Hardcoded edge-case datasets
```

---

## 1. SHORTLISTING MERIT TESTS (Stage 1 — Part A Only)

### 1.1 Basic Functionality
- **test_shortlisting_basic_1_to_5_ratio**
  - Input: 2,500 candidates with distinct Part A scores.
  - Expected: Exactly 500 candidates shortlisted (1:5 ratio).
  - Assertion: Count == 500, all have shortlisted_status='Shortlisted'.

- **test_shortlisting_ranking_desc_by_part_a**
  - Input: 2,500 candidates.
  - Expected: Rank 1 has highest Part A, Rank 2 next highest, etc.
  - Assertion: For each i, candidate[i].part_a >= candidate[i+1].part_a.

- **test_shortlisting_competition_ranking**
  - Input: Candidates with Part A scores: [100, 95, 95, 90, 85].
  - Expected: Ranks [1, 2, 2, 4, 5] (ties share rank, next score skips ahead).
  - Assertion: Rank gaps match count of candidates with strictly higher scores.

### 1.2 Tied Groups at Cutoff (Boundary)
- **test_shortlisting_tied_group_inclusion_small**
  - Input: 500 candidates shortlisted cleanly, then 5 tied candidates at the boundary with Part A=72.5.
  - Expected: All 5 are shortlisted → total 505 (exceeds 1:5 target).
  - Assertion: Shortlist count == 505, all 5 tied candidates present.

- **test_shortlisting_tied_group_inclusion_large**
  - Input: Boundary rank has 50 candidates tied at Part A=75.
  - Expected: All 50 included, shortlist size ~550 (target was 500).
  - Assertion: No candidate is rejected just because they tied at cutoff.

- **test_shortlisting_no_arbitrary_split_of_ties**
  - Input: 15 candidates tied at boundary rank.
  - Expected: All 15 shortlisted, **not** arbitrarily taking first 8 and rejecting last 7.
  - Assertion: Tied group is atomic, no partial inclusion.

### 1.3 Category Rank (Vertical Breakdown)
- **test_category_rank_within_vertical_general**
  - Input: 2,500 candidates, 1,020 tagged as General.
  - Expected: General shortlist = 245 (1:5 of 1,020 = ~204, but 245 per protocol fixed quota).
  - Assertion: General count == 245, category ranks 1-245 within General alone.

- **test_category_rank_within_vertical_sc**
  - Input: 375 SC candidates.
  - Expected: SC shortlist = 90.
  - Assertion: SC count == 90, ranks are 1-90 within SC-only pool.

- **test_category_rank_independent_of_overall_rank**
  - Input: Candidate X is Overall Rank 500 but Category Rank 5 (within SC).
  - Expected: Both ranks coexist correctly, no conflict.
  - Assertion: overall_rank != category_rank, both logically correct per their respective pools.

### 1.4 Vertical Category Absorption
- **test_general_absorption_ignores_underlying_vertical**
  - Input: Candidate with underlying_vertical='SC' but scores high enough for top 245 General.
  - Expected: Candidate absorbed into General (Part A merit overrides category).
  - Assertion: Shortlisted_category == 'General', not 'SC'.

- **test_merit_absorption_prevents_double_counting**
  - Input: 1,020 General + 375 SC = 1,395 total. Top 245 by merit pulled regardless of vertical.
  - Expected: SC candidates in top 245 don't count against SC's 90-seat quota.
  - Assertion: SC quota filled *from remainder after General 245 are taken*, not competing for same seats.

### 1.5 Horizontal Attributes (Karnataka, PWD, Women)
- **test_karnataka_compartmentalized_within_general**
  - Input: 245 shortlisted General candidates, 60 of them flagged Karnataka.
  - Expected: Karnataka count within General = 60 (meeting compartmentalized minimum).
  - Assertion: Count == 60, all 60 are within the 245 General candidates.

- **test_pwd_overall_horizontal_across_verticals**
  - Input: 600 shortlisted (various verticals), 30 flagged PWD.
  - Expected: PWD count = 30, distributed across General/SC/ST/OBC-NCL/EWS.
  - Assertion: PWD not confined to one vertical, can span multiple.

- **test_women_overall_horizontal_derived_from_gender**
  - Input: 600 shortlisted, 188 with gender='Female'.
  - Expected: Women count = 188 (not a separate stored field, derived from gender).
  - Assertion: Women_count == sum(1 for c in shortlist if c.gender == 'Female').

### 1.6 Edge Cases & Errors
- **test_shortlisting_with_zero_part_a_scores**
  - Input: 5 candidates with Part A <= 0 (disqualified per protocol).
  - Expected: Excluded from shortlisting entirely, not ranked.
  - Assertion: Disqualified candidates absent from shortlist, count = 2,495 eligible - 5 = 2,490 (if input was 2,500).

- **test_shortlisting_all_candidates_identical_score**
  - Input: 2,500 candidates all with Part A = 50.
  - Expected: All tied at Rank 1, all shortlisted (no cutoff possible with universal tie).
  - Assertion: Shortlist count == 2,500 (100% inclusion), rank == 1 for all.

- **test_shortlisting_single_candidate**
  - Input: 1 candidate.
  - Expected: Shortlisted (1:5 ratio still applies, 1 > 1/5).
  - Assertion: Count == 1, rank == 1.

---

## 2. FINAL MERIT RANKING TESTS (Stage 2 — Part A + Part B)

### 2.1 Basic Functionality
- **test_final_merit_total_score_calculation**
  - Input: Candidate with Part A=75.5, Part B=40.25.
  - Expected: Total = 75.5 + 40.25 = 115.75.
  - Assertion: total_score == 115.75 (to 2 decimals).

- **test_final_merit_ranking_by_total_desc**
  - Input: 600 shortlisted, ranked by Part A+B descending.
  - Expected: Rank 1 has highest total, Rank 2 next, ..., Rank 600 lowest.
  - Assertion: For each i, candidate[i].total >= candidate[i+1].total.

- **test_final_merit_rank_1_to_n_sequential**
  - Input: 600 shortlisted (no filtered out).
  - Expected: Ranks run 1 to 600.
  - Assertion: min(ranks) == 1, max(ranks) == 600, no gaps if no ties after tiebreak.

### 2.2 Tiebreak Logic: Part B
- **test_tiebreak_part_b_when_total_same**
  - Input: Two candidates, both total=100, one Part B=45, other Part B=40.
  - Expected: Part B=45 ranks higher (Rank 10 vs Rank 11, for example).
  - Assertion: candidate_higher_partb.rank < candidate_lower_partb.rank.

- **test_tiebreak_part_b_multiple_candidates_same_total**
  - Input: 5 candidates all total=100, Part B scores [50, 48, 50, 46, 50].
  - Expected: Sorted by Part B desc → [50, 50, 50, 48, 46], ranks [1, 1, 1, 5, 6] (no, wait — with Part B tiebreak, ranks should be [1, 1, 1, 5, 6] if this is full tiebreak, or all 5 share Rank 1 if not further tiebroken).
  - **Clarification needed:** Do candidates with same Total and Part B share a rank, or does DOB immediately break? (Assuming they do share if both total AND part_b are same.)

### 2.3 Tiebreak Logic: Date of Birth
- **test_tiebreak_dob_when_total_and_partb_same**
  - Input: Two candidates, both total=100, both Part B=45, DOB 1. = '01-01-2005', DOB 2 = '01-01-2006'.
  - Expected: DOB 1 (older) ranks higher.
  - Assertion: older_dob_candidate.rank < younger_dob_candidate.rank.

- **test_tiebreak_dob_older_wins**
  - Input: 4 candidates, all total=95, all Part B=40. DOBs: 2004-05-15, 2005-10-20, 2005-02-01, 2006-12-25.
  - Expected: Sorted by DOB ascending (oldest first), ranks assigned accordingly.
  - Assertion: 2004-05-15 ranks best, 2006-12-25 ranks worst.

### 2.4 Tiebreak Logic: Applicant ID
- **test_tiebreak_applicant_id_when_dob_same**
  - Input: Two candidates, both total=100, both Part B=45, same DOB. IDs: APP-2026-00100, APP-2026-00099.
  - Expected: APP-2026-00099 ranks higher (numerically lower ID).
  - Assertion: id_00099.rank < id_00100.rank.

- **test_tiebreak_applicant_id_lexicographic_or_numeric**
  - Input: IDs [APP-2026-00500, APP-2026-00100, APP-2026-00050].
  - Expected: Sorted numerically (assuming "APP-2026-" prefix stripped and compared as integers).
  - Assertion: Verify behavior is numeric, not lexicographic (00050 < 00100, not "00050" > "00100" as strings).

### 2.5 Complete Tiebreak Chain
- **test_full_tiebreak_chain_total_partb_dob_id**
  - Input: 10 candidates with identical total and part_b scores, varying DOB and ID.
  - Expected: Ranked by DOB asc, then by ID asc for same DOB.
  - Assertion: Chain enforces strict ordering without ties in final rank.

- **test_no_tied_ranks_after_full_tiebreak**
  - Input: 600 shortlisted candidates re-ranked with full tiebreak.
  - Expected: All 600 have distinct ranks 1-600 (no rank value repeated).
  - Assertion: len(set(ranks)) == 600.

### 2.6 Percentile Calculation (if applicable)
- **test_percentile_within_shortlist**
  - Input: 600 candidates ranked 1-600.
  - Expected: Rank 1 → 100th percentile, Rank 300 → 50th percentile, Rank 600 → 0th percentile (approx).
  - Formula: percentile = 100 * (N - rank) / (N - 1).
  - Assertion: Percentile values monotonically decrease with rank, bounds [0, 100).

### 2.7 No Re-filtering at Final Merit
- **test_no_percentile_cutoff_at_final_merit**
  - Input: 600 shortlisted, all re-ranked (no cutoff applied).
  - Expected: All 600 remain in final merit list, regardless of percentile.
  - Assertion: final_merit_list_count == 600 (not reduced by any gate).

### 2.8 Edge Cases
- **test_final_merit_with_all_candidates_same_score**
  - Input: 600 candidates all total=100, all Part B=50, all DOB='01-01-2005'.
  - Expected: Ranked solely by Applicant ID.
  - Assertion: Ranks 1-600 assigned by ID numerically, all other fields identical.

- **test_final_merit_single_candidate**
  - Input: 1 candidate in shortlist.
  - Expected: Rank 1, percentile 100 (by formula).
  - Assertion: rank == 1, percentile == 100.

---

## 3. SEAT ALLOCATION TESTS (Stage 3 — Hard 120-Seat Cap)

### 3.1 Basic Allocation
- **test_seat_allocation_exact_120**
  - Input: 600 ranked candidates, 120 total seats.
  - Expected: Exactly 120 candidates allocated.
  - Assertion: allocated_count == 120, allocation_status='Allocated' for top 120 by rank.

- **test_seat_allocation_respects_final_merit_rank**
  - Input: 600 ranked by Final Merit.
  - Expected: Top 120 by Final Merit Rank get seats (Rank 1-120).
  - Assertion: Allocated candidates = those with final_merit_rank <= 120.

- **test_seat_allocation_allocation_status_field**
  - Input: 600 candidates, 120 seats.
  - Expected: Top 120 have allocation_status='Allocated', rest have 'Not Allocated'.
  - Assertion: Dual validation of count and status field.

### 3.2 Vertical Quota Enforcement
- **test_vertical_quota_general_49**
  - Input: 600 ranked, General-tagged candidates distributed throughout.
  - Expected: Exactly 49 General candidates allocated.
  - Assertion: count(allocated AND vertical='General') == 49.

- **test_vertical_quota_sc_18**
  - Expected: count(allocated AND vertical='SC') == 18.

- **test_vertical_quota_st_9**
  - Expected: count(allocated AND vertical='ST') == 9.

- **test_vertical_quota_obc_ncl_32**
  - Expected: count(allocated AND vertical='OBC-NCL') == 32.

- **test_vertical_quota_ews_12**
  - Expected: count(allocated AND vertical='EWS') == 12.

- **test_vertical_quotas_sum_to_120**
  - Expected: 49 + 18 + 9 + 32 + 12 == 120.

### 3.3 Compartmentalized Karnataka (within each Vertical)
- **test_compartmentalized_karnataka_general_minimum_12**
  - Input: 49 General candidates allocated.
  - Expected: At least 12 have karnataka='Yes'.
  - Assertion: count(allocated AND vertical='General' AND karnataka='Yes') >= 12.

- **test_compartmentalized_karnataka_sc_minimum_4**
  - Expected: count(allocated AND vertical='SC' AND karnataka='Yes') >= 4.

- **test_compartmentalized_karnataka_st_minimum_2**
  - Expected: >= 2.

- **test_compartmentalized_karnataka_obc_ncl_minimum_8**
  - Expected: >= 8.

- **test_compartmentalized_karnataka_ews_minimum_3**
  - Expected: >= 3.

- **test_karnataka_not_allocated_outside_assigned_vertical**
  - Input: A Karnataka-flagged candidate allocated to General.
  - Expected: They count toward General's Karnataka quota, not all-India Karnataka pool.
  - Assertion: Karnataka quota is *per vertical*, not global.

### 3.4 Overall Horizontal: PWD (6 seats total)
- **test_overall_pwd_minimum_6**
  - Input: 120 allocated candidates.
  - Expected: At least 6 have pwd='Yes'.
  - Assertion: count(allocated AND pwd='Yes') >= 6.

- **test_overall_pwd_spans_verticals**
  - Input: 6 PWD candidates allocated.
  - Expected: Distributed across General/SC/ST/OBC-NCL/EWS, not confined to one.
  - Assertion: len(set(vertical for c in allocated if c.pwd=='Yes')) > 1 (ideally).

- **test_pwd_displacement_of_non_pwd**
  - Input: Scenario where a PWD candidate of lower rank displaces a higher-rank non-PWD to fill PWD quota.
  - Expected: Displacement logic applies (detailed in reservation policy tests below).
  - Assertion: Final allocation honors both PWD minimum and overall rank priority.

### 3.5 Overall Horizontal: Women (36 seats total)
- **test_overall_women_minimum_36**
  - Input: 120 allocated candidates.
  - Expected: At least 36 have gender='Female'.
  - Assertion: count(allocated AND gender='Female') >= 36.

- **test_overall_women_spans_verticals**
  - Expected: Women distributed across verticals.
  - Assertion: len(set(vertical for c in allocated if c.gender=='Female')) > 1 (ideally).

### 3.6 Hard 120-Seat Cap (No Tie Inclusion)
- **test_seat_allocation_exactly_120_no_overflow_at_cutoff**
  - Input: 120 top-ranked candidates, Rank 120 unique (no tie).
  - Expected: Exactly 120 allocated, Rank 121+ not included.
  - Assertion: allocated_count == 120 (hard stop, unlike shortlisting's tie-group inclusion).

- **test_seat_allocation_tied_at_rank_120_does_not_all_include**
  - Input: Ranks 1-119 unique, Rank 120 tied between 5 candidates (same total, part_b, dob, id prefix collision scenario).
  - Expected: Only 1 of the 5 tied at Rank 120 is included, bringing total to 120. The other 4 are not allocated.
  - **Note:** This assumes Rank 120 is unique (final tiebreak ensures it). If truly tied in rank value, clarify policy: include all 5 (total 124) or hard cap at 120?
  - **Assumption:** With full tiebreak (DOB, ID), Rank 120 is always unique. Test validates this assumption holds.

### 3.7 Reservation Policy Integration
- **test_merit_absorption_at_allocation_stage**
  - Input: An SC candidate who ranks high enough to be in top 49 (General quota).
  - Expected: Allocated to General, does not consume SC seat.
  - Assertion: allocated_vertical == 'General', not 'SC'.

- **test_vertical_fill_from_remainder_after_absorption**
  - Input: Top 49 include 10 SC-tagged candidates (absorbed into General).
  - Expected: SC quota filled from the next 51-600 ranks (remainder pool), not from top 49.
  - Assertion: SC allocation slots filled from SC-only candidates ranked outside top 49.

### 3.8 Edge Cases
- **test_seat_allocation_with_fewer_candidates_than_seats**
  - Input: 100 ranked candidates (shortlist < seat cap).
  - Expected: All 100 allocated (no seats left empty if candidates available).
  - Assertion: allocated_count == 100.

- **test_seat_allocation_single_candidate**
  - Input: 1 ranked candidate.
  - Expected: Allocated (gets the 1st seat).
  - Assertion: allocated_count == 1.

- **test_seat_allocation_vertical_quota_exceeds_available_candidates**
  - Input: General quota = 49, but only 30 General-tagged candidates in shortlist.
  - Expected: All 30 allocated, 19 General seats left vacant.
  - Assertion: allocated_general == 30, not forced to overfill or error.

- **test_seat_allocation_all_candidates_same_rank_value**
  - Input: All 600 candidates tied (same total, part_b, dob, id).
  - **Note:** Impossible with full tiebreak. If it occurs, indicates data integrity issue.
  - Assertion: Data validation catches and rejects duplicate (total, part_b, dob, id) tuples.

---

## 4. RESERVATION POLICY TESTS

### 4.1 Vertical Category Structure
- **test_vertical_mutual_exclusivity**
  - Input: Single candidate record.
  - Expected: Exactly one vertical tag (General, SC, ST, OBC-NCL, or EWS), not multiple.
  - Assertion: vertical_tag is one of [General, SC, ST, OBC-NCL, EWS], exactly one.

- **test_vertical_quota_proportions**
  - Input: Expected protocol quotas.
  - Expected: General 49 (40.8%), SC 18 (15%), ST 9 (7.5%), OBC-NCL 32 (26.7%), EWS 12 (10%).
  - Assertion: Sums to 120, percentages match protocol doc.

### 4.2 Compartmentalized Karnataka (Vertical × Karnataka Matrix)
- **test_karnataka_minimum_per_vertical_met**
  - Expected: General >= 12, SC >= 4, ST >= 2, OBC-NCL >= 8, EWS >= 3.
  - Assertion: Each quota met independently.

- **test_karnataka_no_global_pool**
  - Input: Karnataka-flagged candidates.
  - Expected: Each counted within their own vertical's Karnataka allocation, not drawn from a shared pool.
  - Assertion: A Karnataka SC candidate fills SC's Karnataka quota, not General's.

- **test_karnataka_displacement_within_vertical**
  - Input: Scenario: General has 10 Karnataka candidates allocated, needs 12. Next-ranked Karnataka-General candidate is Rank 60 (higher rank = better). Non-Karnataka General at Rank 50 exists.
  - Expected: Displacement: Remove Rank-50 non-Karnataka General, add Rank-60 Karnataka General, to fill Karnataka quota.
  - Assertion: Final count: General 49 (unchanged), Karnataka 12 (filled).

### 4.3 Overall Horizontal: PWD
- **test_pwd_independent_of_vertical**
  - Input: PWD flag + vertical flag on same candidate.
  - Expected: PWD is independent attribute (can be SC+PWD, General+PWD, etc.).
  - Assertion: PWD count not confined to one vertical.

- **test_pwd_displacement_prioritizes_rank**
  - Input: PWD quota not met. Rank-30 PWD candidate available, Rank-25 non-PWD allocated.
  - Expected: Displace Rank-25, allocate Rank-30 PWD.
  - Assertion: PWD minimum honored even if pushes down average rank.

- **test_pwd_5_percent_of_120**
  - Expected: 5% of 120 = 6 PWD seats minimum.
  - Assertion: count(pwd='Yes') >= 6.

### 4.4 Overall Horizontal: Women
- **test_women_30_percent_of_120**
  - Expected: 30% of 120 = 36 Women seats minimum.
  - Assertion: count(gender='Female') >= 36.

- **test_women_spans_all_categories**
  - Input: 36 Women allocated.
  - Expected: Distributed across General, SC, ST, OBC-NCL, EWS (ideally all represented).
  - Assertion: At least 2-3 verticals have women allocated.

### 4.5 Interaction of Vertical + Compartmentalized + Overall Horizontal
- **test_candidate_tagged_sc_karnataka_woman_allocated_correctly**
  - Input: Single candidate: vertical='SC', karnataka='Yes', gender='Female'.
  - Expected: Counted in all three quotas: SC (1), SC-Karnataka (1), Women (1), but occupies only 1 seat.
  - Assertion: Same candidate satisfies multiple quota types simultaneously.

- **test_no_double_counting_across_tiers**
  - Input: Same candidate satisfies SC + Karnataka + Women.
  - Expected: Fills 1 seat, not 3.
  - Assertion: Seat count remains 120, not inflated.

---

## 5. TIEBREAK LOGIC TESTS (Dedicated Suite)

### 5.1 Part B Tiebreak
- **test_part_b_tiebreak_strict_ordering**
  - Input: 100 candidates, all total=100, part_b values [50, 48, 50, 45, 50, ...].
  - Expected: Candidates with part_b=50 rank before 48, which rank before 45, etc.
  - Assertion: Ordering strict and transitive.

### 5.2 DOB Tiebreak
- **test_dob_tiebreak_older_first**
  - Input: DOB 1990-01-01, 1995-06-15, 2000-12-31 (all other fields equal).
  - Expected: 1990 ranks best, 2000 ranks worst.
  - Assertion: Older DOB always preferred.

- **test_dob_leap_year_handling**
  - Input: DOB 2004-02-29 (leap year), 2004-03-01 (next day).
  - Expected: Leap day correctly recognized, ordering valid.
  - Assertion: No date parsing errors, comparison works.

- **test_dob_boundary_same_day_different_year**
  - Input: 2003-05-15 vs 2004-05-15 (exactly 1 year apart).
  - Expected: 2003 older, ranks higher.
  - Assertion: Verified via date ordinal comparison.

### 5.3 Applicant ID Tiebreak
- **test_applicant_id_numeric_ordering**
  - Input: IDs [APP-2026-00500, APP-2026-00099, APP-2026-00200] with same total/part_b/dob.
  - Expected: Ordered as 00099 < 00200 < 00500 (numerically).
  - Assertion: Numeric sort, not lexicographic.

- **test_applicant_id_format_parsing**
  - Input: Various ID formats (APP-2026-XXXXX).
  - Expected: Extract numeric portion correctly, compare.
  - Assertion: No parsing errors, consistent extraction.

### 5.4 Tiebreak Chain Precedence
- **test_tiebreak_precedence_total_before_partb**
  - Input: Candidate A (total=100.5, part_b=40), Candidate B (total=100.4, part_b=50).
  - Expected: Candidate A ranks higher (total alone decides, part_b not consulted).
  - Assertion: total comparison is first and dominant.

- **test_tiebreak_precedence_partb_before_dob**
  - Input: Candidate A (total=100, part_b=50, dob=2000), Candidate B (total=100, part_b=49, dob=1990).
  - Expected: Candidate A ranks higher (part_b=50 > 49, dob not consulted).
  - Assertion: part_b comparison is second and overrides dob.

- **test_tiebreak_precedence_dob_before_id**
  - Input: Candidate A (total=100, part_b=45, dob=1990, id=APP-2026-00500), Candidate B (same total/part_b, dob=1991, id=APP-2026-00099).
  - Expected: Candidate A ranks higher (dob=1990 older, id not consulted).
  - Assertion: dob comparison is third and overrides id.

---

## 6. BOUNDARY CONDITION TESTS

### 6.1 Cutoff Boundaries in Shortlisting
- **test_shortlisting_boundary_just_before_tie**
  - Input: Cutoff at Rank 500, rank 501 starts a 10-candidate tie.
  - Expected: Only 500 shortlisted (tie group is after cutoff).
  - Assertion: Shortlist count == 500.

- **test_shortlisting_boundary_within_tie_group**
  - Input: Cutoff at Rank 500, ranks 490-510 are tied (same part_a), all 21 candidates must be included.
  - Expected: Shortlist count >= 490 (includes all of tie group).
  - Assertion: Entire tied group included.

- **test_shortlisting_boundary_1_percent**
  - Input: Exactly 25 candidates (1% of 2,500).
  - Expected: Shortlist ratio 1:5 → 5 candidates. If no tie at boundary, exactly 5.
  - Assertion: Ratio applied even at micro scale.

### 6.2 Cutoff Boundaries in Final Merit
- **test_final_merit_rank_1_candidate**
  - Input: 600 ranked, top rank (Rank 1) allocated.
  - Expected: Rank 1 candidate has highest total score.
  - Assertion: Verified via score comparison.

- **test_final_merit_rank_120_exactly**
  - Input: 600 ranked.
  - Expected: Rank 120 candidate is last to be allocated.
  - Assertion: Rank 120 allocated, Rank 121+ not allocated.

- **test_final_merit_rank_600_last**
  - Input: 600 ranked.
  - Expected: Rank 600 has lowest total score.
  - Assertion: Last rank verified.

### 6.3 Zero/Empty Edge Cases
- **test_shortlisting_zero_candidates**
  - Input: No candidates.
  - Expected: Error or empty result, not crash.
  - Assertion: Graceful handling (either exception raised or empty list returned).

- **test_seat_allocation_zero_candidates_shortlisted**
  - Input: Shortlist is empty.
  - Expected: No seats allocated, all 120 vacant.
  - Assertion: allocated_count == 0, no crash.

- **test_shortlisting_zero_seats_to_allocate**
  - Input: Hypothetical scenario where seat count = 0.
  - Expected: No candidates allocated (edge case validation).
  - Assertion: Handles gracefully.

### 6.4 Maximum/Overshoot Cases
- **test_shortlisting_all_candidates_single_score**
  - Input: All 2,500 tied at same part_a.
  - Expected: All shortlisted (entire population), ratio becomes 1:1.
  - Assertion: Shortlist count == 2,500.

- **test_seat_allocation_shortlist_smaller_than_seats**
  - Input: 100 shortlisted, 120 seats.
  - Expected: All 100 allocated, 20 seats vacant.
  - Assertion: No overfill, allocation_count == 100.

---

## 7. DATA CONSISTENCY & INTEGRITY TESTS

### 7.1 Cross-Stage Consistency
- **test_shortlisted_candidates_in_final_merit**
  - Input: 600 shortlisted candidates.
  - Expected: All 600 appear in Final Merit List with same ID.
  - Assertion: set(shortlist_ids) ⊆ set(final_merit_ids), and |intersection| == 600.

- **test_allocated_candidates_in_final_merit**
  - Input: 120 allocated candidates.
  - Expected: All 120 in Final Merit List.
  - Assertion: set(allocated_ids) ⊆ set(final_merit_ids).

- **test_final_merit_rank_stable_across_exports**
  - Input: Generate Final Merit twice from same data.
  - Expected: Identical ranks, same order.
  - Assertion: Both outputs bitwise identical (or at least logically equivalent).

### 7.2 Field Value Validity
- **test_total_score_precision**
  - Input: Part A=75.25, Part B=40.75.
  - Expected: Total == 116.00 (exact, no rounding artifacts).
  - Assertion: Precision maintained to 2 decimals.

- **test_rank_no_duplicates**
  - Input: 600 candidates in Final Merit.
  - Expected: All 600 ranks are unique (1-600).
  - Assertion: len(set(ranks)) == 600.

- **test_rank_no_gaps**
  - Input: 600 candidates ranked (with tiebreak, should be fully sequential).
  - Expected: Rank sequence is [1, 2, 3, ..., 600].
  - Assertion: No rank value skipped (e.g., 1,2,3,5,6 would indicate gap).

- **test_vertical_values_valid**
  - Input: All allocated candidates.
  - Expected: Vertical is one of [General, SC, ST, OBC-NCL, EWS].
  - Assertion: No invalid values, no nulls.

- **test_karnataka_boolean_not_string**
  - Input: karnataka field.
  - Expected: True/False (boolean), not 'Yes'/'No' (string) [if DB design specifies boolean].
  - Assertion: Type check (adapt if schema uses string).

- **test_dob_valid_dates**
  - Input: All DOB fields.
  - Expected: Valid date format (YYYY-MM-DD), all dates in past (before today).
  - Assertion: Date parsing succeeds, all dob <= today.

- **test_applicant_id_format**
  - Input: All IDs.
  - Expected: Matches pattern APP-YYYY-NNNNN (e.g., APP-2026-00287).
  - Assertion: Regex validation passes.

### 7.3 Quota Accuracy
- **test_all_quotas_at_stage_1_v_stage_3**
  - Expected: Shortlist quotas (General 245, SC 90, ...) >> Seat quotas (General 49, SC 18, ...).
  - Assertion: 1:5 ratio visibly maintained (shortlist size >> seat size in all categories).

- **test_karnataka_quota_consistency**
  - Input: Shortlist has 151 Karnataka (604 total shortlist, 25% ≈ expected).
  - Expected: Seat allocation has ~32 Karnataka (120 seats, ~27% expected). Ratio consistent.
  - Assertion: Percentage consistency within ±5%.

---

## 8. ERROR HANDLING & VALIDATION TESTS

### 8.1 Invalid Input Data
- **test_missing_part_a_score**
  - Input: Candidate with part_a = None/NULL.
  - Expected: Error raised or candidate skipped with warning.
  - Assertion: System does not crash, invalid record handled.

- **test_missing_part_b_score**
  - Input: Candidate in shortlist with part_b = None.
  - Expected: Error in Final Merit stage, cannot compute total.
  - Assertion: Appropriate error message, no silent failure.

- **test_negative_scores**
  - Input: Candidate with part_a = -5 (invalid per protocol).
  - Expected: Rejected/disqualified.
  - Assertion: Not shortlisted, marked as ineligible.

- **test_score_exceeds_max**
  - Input: Candidate with part_a = 105 (max = 100).
  - Expected: Validation error or data cleansing applied.
  - Assertion: Handled gracefully.

- **test_missing_vertical_tag**
  - Input: Candidate with vertical = None.
  - Expected: Default to 'General' or error.
  - Assertion: Behavior defined and consistent.

- **test_missing_dob**
  - Input: Candidate with dob = None.
  - Expected: Cannot apply DOB tiebreak, error raised.
  - Assertion: System requires dob for tiebreak logic.

- **test_duplicate_applicant_id**
  - Input: Two candidates with same ID (data corruption).
  - Expected: Error detected, one flagged as duplicate.
  - Assertion: ID uniqueness enforced.

- **test_invalid_date_format_dob**
  - Input: dob = '2005-13-32' (invalid month/day).
  - Expected: Date parsing error, record rejected.
  - Assertion: Input validation catches malformed dates.

### 8.2 Boundary Violations
- **test_seat_allocation_exceeds_120**
  - Input: Algorithm produces 121 allocations (should be hard 120).
  - Expected: Error or warning, audit log generated.
  - Assertion: Hard constraint enforced.

- **test_vertical_quota_exceeds_target**
  - Input: General quota = 49, but 60 allocated (data bug in allocation logic).
  - Expected: Validation detects overage, error raised.
  - Assertion: Quota validation is strict.

- **test_karnataka_quota_exceeds_vertical_size**
  - Input: General 49 seats, karnataka_quota = 30 (impossible, > vertical size).
  - Expected: Configuration error detected.
  - Assertion: Pre-allocation validation catches impossible quotas.

### 8.3 Logic Errors
- **test_allocated_candidate_has_rank_outside_top_120**
  - Input: Allocated candidate has rank 500 (should be <= 120).
  - Expected: Data integrity error, audit trail.
  - Assertion: Allocated candidates verified to be in top 120.

- **test_shortlisted_candidate_not_in_final_merit**
  - Input: Candidate in Shortlist but missing from Final Merit.
  - Expected: Reconciliation error, missing record flag.
  - Assertion: Completeness check catches lost records.

- **test_final_merit_candidate_not_from_shortlist**
  - Input: Final Merit includes candidate not in Shortlist.
  - Expected: Data corruption error.
  - Assertion: Final Merit sourced only from Shortlist.

---

## 9. PERFORMANCE & LOAD TESTS

### 9.1 Scaling Tests
- **test_shortlisting_performance_2500_candidates**
  - Input: Full 2,500 candidate dataset.
  - Expected: Completes in < 5 seconds (benchmark).
  - Assertion: Runtime measured, logged, passes threshold.

- **test_final_merit_performance_600_candidates**
  - Input: 600 shortlisted.
  - Expected: Completes in < 1 second.
  - Assertion: Re-ranking is fast.

- **test_seat_allocation_performance_120_allocation**
  - Input: 600 ranked, 120-seat allocation.
  - Expected: Completes in < 500ms.
  - Assertion: Reservation policy application is efficient.

### 9.2 Memory Tests
- **test_shortlisting_memory_usage**
  - Input: 2,500 candidates.
  - Expected: Memory footprint < 500MB (rough estimate, adjust per environment).
  - Assertion: No memory leaks, efficient data structures.

- **test_large_tied_group_performance**
  - Input: 500 candidates tied at boundary rank.
  - Expected: Handles large tie-group smoothly, completes in reasonable time.
  - Assertion: No exponential blowup in complexity.

### 9.3 Concurrency Tests (if applicable)
- **test_concurrent_merit_generation**
  - Input: Two simultaneous merit-list generation requests for same data.
  - Expected: Both complete with identical results, no race conditions.
  - Assertion: Results deterministic, no corrupted state.

- **test_allocation_under_lock**
  - Input: Allocation process + concurrent read attempt.
  - Expected: Reads blocked or return stale data (per isolation policy).
  - Assertion: No dirty reads, consistency maintained.

---

## 10. REAL-WORLD SCENARIO TESTS

### 10.1 Typical Admission Cycle
- **test_full_pipeline_2500_to_600_to_120**
  - Input: 2,500 candidates imported.
  - Process: Shortlist → Final Merit → Allocate.
  - Expected: All three stages complete, counts are 600, 600, 120 respectively.
  - Assertion: End-to-end pipeline success, no data loss.

### 10.2 Revision/Re-run Scenario
- **test_shortlist_regeneration_after_score_update**
  - Input: Update one candidate's Part A score.
  - Process: Regenerate shortlist.
  - Expected: Candidate's new rank reflects updated score.
  - Assertion: Rank recalculated correctly, other candidates unaffected.

- **test_final_merit_regeneration_after_part_b_release**
  - Input: Part B scores released after shortlist finalized.
  - Process: Regenerate Final Merit.
  - Expected: Shortlist unchanged, ranks re-ordered by cumulative score.
  - Assertion: Shortlist stability, rank fluidity demonstrated.

### 10.3 Dispute/Appeal Scenario
- **test_candidate_score_correction_impact**
  - Input: Candidate's Part A score corrected (e.g., 70 → 75).
  - Expected: Candidate re-ranks, may move from Not Shortlisted to Shortlisted.
  - Assertion: Correction propagates through all stages.

- **test_dob_correction_tiebreak_impact**
  - Input: Candidate's DOB corrected (e.g., 2005 → 2004).
  - Expected: May shift Final Merit rank if tied with others.
  - Assertion: DOB tiebreak reflects correction.

### 10.4 Retrospective Audit
- **test_audit_trail_candidate_progression**
  - Input: Single candidate (e.g., APP-2026-00500).
  - Query: Trace through all stages (Shortlist → Final Merit → Allocated).
  - Expected: Audit log shows stage entry, rank, quota met, final status.
  - Assertion: Full traceability for compliance/appeals.

---

## 11. PROTOCOL COMPLIANCE TESTS

### 11.1 Adherence to NLSAT-LLB Protocol Document
- **test_protocol_vertical_quotas_exact**
  - Expected: General 49/120 (40.83%), SC 18/120 (15%), ST 9/120 (7.5%), OBC-NCL 32/120 (26.67%), EWS 12/120 (10%).
  - Assertion: Matches protocol section 3.2 verbatim.

- **test_protocol_karnataka_compartmentalization**
  - Expected: Karnataka carved out proportionally within each vertical, not globally.
  - Assertion: Matches protocol section 4.1.

- **test_protocol_women_30_percent**
  - Expected: 36/120 ≈ 30%.
  - Assertion: Matches protocol section 4.3.

- **test_protocol_pwd_5_percent**
  - Expected: 6/120 = 5%.
  - Assertion: Matches protocol section 4.2.

- **test_protocol_merit_absorption_rule**
  - Expected: Top-merit candidates absorbed into General regardless of underlying vertical.
  - Assertion: Matches protocol section 2.1 example.

- **test_protocol_percentile_cutoffs**
  - Expected: (If applicable) General/EWS >= 75th, SC/ST/OBC/PWD >= 40th.
  - Assertion: Matches protocol section 5.

- **test_protocol_tiebreak_chain**
  - Expected: Part A competition rank (ties allowed) → Part B → DOB → ID.
  - Assertion: Matches protocol + stated tiebreak rule.

### 11.2 Protocol Example Walkthrough
- **test_protocol_worked_example_ranks**
  - Input: Re-create protocol's own worked example (if provided).
  - Expected: Output matches protocol doc exactly.
  - Assertion: Reference test validates implementation against authoritatively known results.

---

## 12. REGRESSION TEST SUITE

### 12.1 Known Bugs (Fixed)
- **test_regression_split_tie_group_bug**
  - Input: 15 candidates tied at shortlist boundary.
  - Expected: All 15 included (regression ensures earlier "split half arbitrarily" bug doesn't resurface).
  - Assertion: Regression guard against re-introduction of bug.

- **test_regression_total_score_truncation**
  - Input: Scores with decimal places (e.g., 117.75).
  - Expected: Preserved as float, not truncated to int.
  - Assertion: Ensures Seat Allocation Total Score field remains Float-typed.

- **test_regression_rank_not_row_number**
  - Input: 600 candidates with tied total + part_b.
  - Expected: Tied candidates share same rank (RANK function), not assigned sequential values (ROW_NUMBER function).
  - Assertion: Regression ensures rank semantics correct.

- **test_regression_dob_tiebreak_applied**
  - Input: Two candidates with same total and part_b, different DOB.
  - Expected: Older DOB ranks higher (regression ensures DOB tiebreak not omitted).
  - Assertion: DOB tiebreak actively applied.

---

## PYTEST CONFIGURATION & FIXTURES

### conftest.py Structure
```python
import pytest
from fixtures.candidate_fixtures import (
    sample_2500_candidates,
    sample_600_shortlisted,
    sample_120_allocated,
    candidate_with_exact_tie,
    candidates_tied_at_boundary,
)
from fixtures.score_generators import generate_realistic_scores, generate_edge_case_scores

@pytest.fixture(scope="module")
def db_session():
    """Setup/teardown DB for integration tests."""
    # Initialize test DB
    # ...
    yield session
    # Cleanup

@pytest.fixture
def shortlist_stage(db_session, sample_2500_candidates):
    """Precomputed shortlist for reuse across tests."""
    return shortlist_merit(sample_2500_candidates)

@pytest.fixture
def final_merit_stage(db_session, shortlist_stage):
    """Precomputed Final Merit for reuse."""
    return final_merit_ranking(shortlist_stage)

@pytest.fixture
def allocation_stage(db_session, final_merit_stage):
    """Precomputed Seat Allocation."""
    return seat_allocation(final_merit_stage)
```

### Test Markers (for selective runs)
```
@pytest.mark.unit  # Fast, isolated tests
@pytest.mark.integration  # Cross-stage tests
@pytest.mark.boundary  # Edge cases
@pytest.mark.performance  # Load/stress tests
@pytest.mark.regression  # Known bug guards
@pytest.mark.protocol  # Protocol compliance
@pytest.mark.slow  # Long-running tests
```

### Example CLI Runs
```bash
# Run all unit tests
pytest -m unit -v

# Run only shortlisting tests
pytest tests/test_shortlisting_merit.py -v

# Run boundary tests with detailed output
pytest -m boundary --tb=short

# Run with performance profiling
pytest tests/test_performance_load.py --profile

# Run full suite (with slow tests)
pytest -v

# Parallel run (if pytest-xdist installed)
pytest -n auto -m "not slow"
```

---

## SUCCESS CRITERIA

All tests must pass for:
1. **Functional Correctness:** Ranks, quotas, allocations exact per protocol.
2. **Data Integrity:** No lost records, duplicates, or corrupted state across stages.
3. **Boundary Resilience:** Tied groups handled atomically, no arbitrary exclusions.
4. **Performance:** All operations complete within defined thresholds.
5. **Auditability:** Full trace of each candidate through pipeline, with timestamps.
6. **Protocol Compliance:** All protocol sections validated via test assertions.

---

## NOTES FOR DEVELOPMENT TEAM

- **Test Data:** Use both realistic (sampled from real scores) and synthetic edge-case data.
- **Isolation:** Unit tests must not depend on external services (mock DB where possible).
- **Parametrization:** Use `@pytest.mark.parametrize` for combinatorial scenario testing (e.g., all vertical combinations × all tiebreak precedences).
- **Logging:** Capture detailed logs for each test, especially failures — helps with root-cause analysis.
- **CI/CD:** Integrate into pipeline; fail deployment if test coverage < 90% or any critical test fails.
- **Regression Suite:** Run before every release to catch re-introduced bugs.
