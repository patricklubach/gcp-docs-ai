#!/usr/bin/env bash
# Verify that every expected_url in the golden set resolves.
#
# An expected_url that 404s or redirects elsewhere silently depresses recall@k and
# makes a working retriever look broken, so run this before trusting any metric
# computed against questions.yaml — and again on a schedule, because Google moves
# documentation pages.
#
# Usage:  ./verify-urls.sh [questions.yaml]
# Exit:   0 = all URLs OK, 1 = at least one failed
#
# Requires: python3 with PyYAML, curl.

set -uo pipefail
FILE="${1:-$(dirname "$0")/questions.yaml}"
UA="gcp-docs-ai-golden-verifier/1.0 (+https://github.com/patricklubach/gcp-docs-ai)"

mapfile -t ROWS < <(python3 -c '
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
for q in d["questions"]:
    for u in q["expected_urls"]:
        print(f"{q[\"id\"]}\t{u}")
' "$FILE")

total=${#ROWS[@]}
fail=0
redirect=0

printf "Verifying %d URLs from %s\n\n" "$total" "$FILE"

for row in "${ROWS[@]}"; do
  qid="${row%%$'\t'*}"
  url="${row#*$'\t'}"

  # -L to follow redirects, then report the URL we actually landed on.
  read -r code final < <(curl -sS -L --max-time 30 -A "$UA" \
      -o /dev/null -w '%{http_code} %{url_effective}' "$url" 2>/dev/null || echo "000 -")

  if [[ "$code" == "200" && "$final" == "$url" ]]; then
    printf '  ok        %-12s %s\n' "$qid" "$url"
  elif [[ "$code" == "200" ]]; then
    printf '  REDIRECT  %-12s %s\n            -> %s\n' "$qid" "$url" "$final"
    redirect=$((redirect + 1))
  else
    printf '  FAIL %-4s %-12s %s\n' "$code" "$qid" "$url"
    fail=$((fail + 1))
  fi
done

printf '\n%d URLs: %d ok, %d redirected, %d failed\n' \
  "$total" "$((total - fail - redirect))" "$redirect" "$fail"

if (( redirect > 0 )); then
  echo "Redirects are not failures, but update questions.yaml to the final URL so the"
  echo "expected_urls match what the crawler will canonicalize to (see T-1.2)."
fi

(( fail == 0 ))
