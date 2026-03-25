#!/bin/bash
set -euo pipefail



mkdir -p logs

/home/data/RFdiffusion/RFdiffusion/scripts/run_inference.py \
inference.output_prefix=/home/cs/SH/binder_llm/data/jobs/job-20260313-160724/outputs/rfdiffusion/ \
inference.input_pdb=/home/cs/SH/binder_llm/data/targets/1yjd_monomer.pdb \
'contigmap.contigs=[C1-118/0 60-80]' \
'ppi.hotspot_res=[C34]' \
inference.num_designs=100 \
denoiser.noise_scale_ca=1.0 \
denoiser.noise_scale_frame=1.0