#!/bin/bash
set -euo pipefail

source ~/miniconda3/etc/profile.d/conda.sh
conda activate rfdiffusion

mkdir -p logs

python /opt/RFdiffusion/scripts/run_inference.py \
  inference.input_pdb="/home/cs/SH/binder_llm/data/targets/1yjd_monomer.pdb" \
  inference.num_designs=50 \
  contigmap.length=80 \
  
  inference.output_prefix="/home/cs/SH/binder_llm/data/jobs/job-20260313-134721/outputs/rfdiffusion/design"