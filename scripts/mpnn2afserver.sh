#!/bin/bash

# Usage:
# ./mpnn2afserver_fixed.sh --dir fa_dir --max_job 10 [--fa extra.fa]

while [[ $# -gt 0 ]]; do
  case $1 in
    --dir)
      DIR="$2"; shift 2 ;;
    --max_job)
      MAX_JOB="$2"; shift 2 ;;
    --fa)
      EXTRA_FA="$2"; shift 2 ;;
    *)
      echo "Usage: $0 --dir <dir> --max_job <num> [--fa extra.fa]"
      exit 1 ;;
  esac
done

[[ -z "$DIR" || -z "$MAX_JOB" ]] && { echo "--dir and --max_job required"; exit 1; }
[[ ! -d "$DIR" ]] && { echo "Invalid dir"; exit 1; }

# Optional extra chain
extra_seq=""
if [[ -n "$EXTRA_FA" ]]; then
  seq=$(grep -v '^>' "$EXTRA_FA" | tr -d '\r\n')
  extra_seq=$(cat <<EOF2
      {
        "proteinChain": {
          "sequence": "$seq",
          "count": 1
        }
      }
EOF2
)
fi

batch=1
total_job=0
json="$DIR/batch_${batch}.json"
first_in_batch=1

close_batch () {
  echo "]" >> "$json"
}

for fa in "$DIR"/*.fa; do
  [[ -e "$fa" ]] || continue
  base=$(basename "$fa" .fa)

  while IFS=$'\t' read -r tag base job_id seq; do
    ((total_job++))

    # Open a new batch file only when we actually have content to write.
    if [[ $first_in_batch -eq 1 ]]; then
      echo "[" > "$json"
    else
      echo "," >> "$json"
    fi
    first_in_batch=0

    cat >> "$json" <<EOF2
  {
    "name": "${base}_job_${job_id}",
    "modelSeeds": [],
    "sequences": [
      {
        "proteinChain": {
          "sequence": "$seq",
          "count": 1
        }
      }$( [[ -n "$extra_seq" ]] && echo ",")
$( [[ -n "$extra_seq" ]] && echo "$extra_seq" )
    ]
  }
EOF2

    if (( total_job % MAX_JOB == 0 )); then
      close_batch
      ((batch++))
      json="$DIR/batch_${batch}.json"
      first_in_batch=1
    fi

  done < <(
    awk -v base="$base" '
    /^>/ {
      if (seq != "") emit()
      seq=""
      next
    }
    {
      seq = seq $0
    }
    END {
      if (seq != "") emit()
    }
    function emit() {
      seq_count++
      if (seq_count == 1) { seq=""; return }  # skip first sequence
      file_job++
      printf "JOB\t%s\t%d\t%s\n", base, file_job, seq
      seq=""
    }
    ' "$fa"
  )
done

if [[ $first_in_batch -eq 0 ]]; then
  close_batch
fi
