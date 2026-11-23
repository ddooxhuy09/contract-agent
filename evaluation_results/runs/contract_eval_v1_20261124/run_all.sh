#!/bin/sh
# v1.2: risk_flagger thêm luật theo chủ đề + phân loại phát hiện khi có Điều điều chỉnh. Chạy một lần trên bộ test đóng băng.
set -e
export DATABASE_URL=postgresql://contractlens:contractlens@127.0.0.1:5434/contractlens PYTHONUTF8=1
RD=evaluation_results/runs/contract_eval_v1_20261124
LEGAL_RETRIEVAL_MODE=vector python -m evaluation.contract_eval_v1.run retrieval --run-dir $RD --label vector > $RD/retrieval_vector.log 2>&1
LEGAL_RETRIEVAL_MODE=hybrid python -m evaluation.contract_eval_v1.run retrieval --run-dir $RD --label hybrid > $RD/retrieval_hybrid.log 2>&1
python -m evaluation.contract_eval_v1.run generation --run-dir $RD --system-version v1.2 > $RD/generation.log 2>&1
python -m evaluation.contract_eval_v1.run judge --run-dir $RD > $RD/judge.log 2>&1
echo ALL_DONE
