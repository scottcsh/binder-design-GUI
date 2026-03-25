#!/bin/bash

OUTPUT="results.csv"
DIR=""
IPTM_THRESHOLD=""
PTM_THRESHOLD=""
SCORE_THRESHOLD=""
PAE_THRESHOLD=""
MAX_OUTPUT=""
CHAIN_ID=""

# Option parsing
while [[ $# -gt 0 ]]; do
  case $1 in
    --dir) DIR="$2"; shift 2 ;;
    --out) OUTPUT="$2"; shift 2 ;;
    --iptm) IPTM_THRESHOLD="$2"; shift 2 ;;
    --ptm) PTM_THRESHOLD="$2"; shift 2 ;;
    --score) SCORE_THRESHOLD="$2"; shift 2 ;;
    --pae) PAE_THRESHOLD="$2"; shift 2 ;;
    --max_output) MAX_OUTPUT="$2"; shift 2 ;;
    --chain_id) CHAIN_ID="$2"; shift 2 ;;
    --help)
      echo "Usage: $0 --dir <json directory> [--out <output filename>] [--iptm <threshold>] [--ptm <threshold>] [--score <threshold>] [--pae <threshold>] [--chain_id <A-E>] [--max_output <N>] "
      echo ""
      echo "Options:"
      echo "  --dir         Root directory containing JSON files (required)"
      echo "  --out         Output CSV filename (optional, default: results.csv)"
      echo "  --iptm        Minimum iptm value (optional)"
      echo "  --ptm         Minimum ptm value (optional)"
      echo "  --score       Minimum ranking_score value (optional)"
      echo "  --pae         Maximum allowed chain_pair_pae_min value (optional)"
      echo "  --chain_id    Chain ID (A–E) to select diagonal chain_pair_pae_min value"
      echo "  --max_output  Limit output to top N entries sorted by average(iptm, ptm, score)"
      echo "  --help        Show this help message"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [ -z "$DIR" ]; then
  echo "You must specify a directory."
  exit 1
fi

# chain_id → index (A=0, B=1, ..., E=4)
if [ -n "$CHAIN_ID" ]; then
  IDX=$(printf "%d" "'$CHAIN_ID")
  IDX=$((IDX - 65))
fi

if [ -n "$CHAIN_ID" ] && { [ "$IDX" -lt 0 ] || [ "$IDX" -gt 4 ]; }; then
  echo "Invalid --chain_id: $CHAIN_ID (must be A–E)"
  exit 1
fi

TMPFILE=$(mktemp)

# Collect data
find "$DIR" -type f -name "*summary_confidences*.json" \
| grep -vE '_job_[0-9]+_summary_confidences\.json$' \
| while read FILE; do
    iptm=$(jq '.iptm' "$FILE")
    ptm=$(jq '.ptm' "$FILE")
    ranking_score=$(jq '.ranking_score' "$FILE")

    if [ -n "$CHAIN_ID" ]; then
        pae_second=$(jq ".chain_pair_pae_min[$IDX][$IDX]" "$FILE")
    else
        pae_second=$(jq '.chain_pair_pae_min[0][1]' "$FILE")
    fi

    pass=true
    if [ -n "$IPTM_THRESHOLD" ] && (( $(echo "$iptm < $IPTM_THRESHOLD" | bc -l) )); then pass=false; fi
    if [ -n "$PTM_THRESHOLD" ] && (( $(echo "$ptm < $PTM_THRESHOLD" | bc -l) )); then pass=false; fi
    if [ -n "$SCORE_THRESHOLD" ] && (( $(echo "$ranking_score < $SCORE_THRESHOLD" | bc -l) )); then pass=false; fi
    if [ -n "$PAE_THRESHOLD" ] && (( $(echo "$pae_second >= $PAE_THRESHOLD" | bc -l) )); then pass=false; fi

    if [ "$pass" = true ]; then
        avg=$(echo "($iptm + $ptm + $ranking_score)/3" | bc -l | tr -d ' \n')
        # keep avg only for sorting, not in final output
        echo "$(basename "$FILE"),$iptm,$ptm,$ranking_score,$pae_second,$avg" >> "$TMPFILE"
    fi
done

# Sort by average desc, limit, then sort by filename asc

{
  FINAL=$(mktemp)

  if [ -n "$MAX_OUTPUT" ]; then
    awk -F',' '{print $6 "," $0}' "$TMPFILE" \
    | sort -t',' -k1,1nr \
    | head -n "$MAX_OUTPUT" > "$FINAL"
  else
    awk -F',' '{print $6 "," $0}' "$TMPFILE" \
    | sort -t',' -k1,1nr > "$FINAL"
  fi

	echo "Final jobs"
	awk -F',' '{print $2}' "$FINAL" \
	| sed -n 's/^\(.*_job_\([0-9]\+\)\).*/\1 \2/p' \
	| awk '{
		job=$1
		num=$2
		sub(/_job_[0-9]+$/, "", job)
		print job, num, $1
	  }' \
	| sort -k1,1 -k2,2n \
	| awk '{print $3}' \
	| uniq

  echo "-----------------------------------------------------------------"

  echo "filename,avg,iptm,ptm,ranking_score,pae_second"

  awk -F',' '{
      printf "%s,%.2f,%s,%s,%s,%s\n",
             $2,$7,$3,$4,$5,$6
    }' "$FINAL"

  rm "$FINAL"
} | column -t -s, > "$OUTPUT"

rm "$TMPFILE"

echo "Results saved to $OUTPUT"

