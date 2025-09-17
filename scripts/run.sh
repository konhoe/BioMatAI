#!/usr/bin/env bash
set -euo pipefail

# --- 경로 설정(필요시 아래 1줄만 바꾸면 됨) ---
ROSETTA_HOME="${ROSETTA_HOME:-/Users/junyoung/Desktop/BioMatAI/rosetta/rosetta.binary.m1.release-371/main}"

# 프로젝트 루트/입출력 경로 자동 인식
ROOT="$(cd "$(dirname "$0")/.."; pwd)"
IN="$ROOT/input"
OUTROOT="$ROOT/output"
LOGDIR="$ROOT/logs"

# 입력/출력
PDB="${PDB:-$IN/merged_A_B.pdb}"   # 합친 복합체 PDB (체인 A=단백질, B=표면)
PARTNERS="${PARTNERS:-A_B}"        # 체인 파트너 지정
NSTRUCT="${NSTRUCT:-50}"           # 생성할 포즈 수
STAMP="$(date +%y%m%d_%H%M%S)"
OUTDIR="$OUTROOT/surface_dock_${STAMP}"  # 이름 변경
SCOREFILE="$OUTDIR/score.sc"
LOG="$LOGDIR/surface_docking_${STAMP}.log"

# surface vectors 파일
SURF_VECTORS="$IN/surface_vectors.txt"

# 바이너리 - surface_docking으로 변경
BIN="$ROSETTA_HOME/source/bin/surface_docking.static.macosclangrelease"
# 없으면 non-static 버전 시도
if [[ ! -f "$BIN" ]]; then
  BIN="$ROSETTA_HOME/source/bin/surface_docking.macosclangrelease"
fi

DB="$ROSETTA_HOME/database"

mkdir -p "$OUTDIR" "$LOGDIR"

# 존재 확인
if [[ ! -f "$BIN" ]]; then 
  echo "[ERROR] surface_docking not found. Compile it first:"
  echo "  cd $ROSETTA_HOME/source"
  echo "  ./scons.py -j8 mode=release bin/surface_docking.macosclangrelease"
  exit 1
fi

[[ -f "$DB/scoring/score_functions/EnvPairPotential/env_log.txt" ]] || { echo "[ERROR] DB path wrong: $DB"; exit 1; }
[[ -f "$PDB" ]] || { echo "[ERROR] PDB not found: $PDB"; exit 1; }

# surface_vectors.txt 생성 (없으면)
if [[ ! -f "$SURF_VECTORS" ]]; then
  echo "[INFO] Creating default surface_vectors.txt"
  echo "0.0 0.0 1.0" > "$SURF_VECTORS"
fi

echo "[INFO] Using PDB:          $PDB"
echo "[INFO] Surface vectors:    $SURF_VECTORS"
echo "[INFO] Partners:          $PARTNERS"
echo "[INFO] Output dir:        $OUTDIR"
echo "[INFO] Log file:          $LOG"

# resfile 있으면 옵션 추가
EXTRA_OPTS=()
if [[ -f "$ROOT/dock.resfile" ]]; then
  echo "[INFO] Using resfile: $ROOT/dock.resfile"
  EXTRA_OPTS+=( -packing:resfile "$ROOT/dock.resfile" )
fi

# 실행 - surface_docking 전용 옵션 추가
"$BIN" \
  -database "$DB" \
  -s "$PDB" \
  -include_surfaces \
  -in:file:surface_vectors "$SURF_VECTORS" \
  -docking:partners "$PARTNERS" \
  -docking:dock_pert 3 8 \
  -docking:spin \
  -docking:randomize1 \
  -docking:randomize2 \
  -use_ellipsoidal_randomization true \
  -packing:use_input_sc \
  -ex1 \
  -ex2aro \
  -nstruct "$NSTRUCT" \
  -out:file:scorefile "$SCOREFILE" \
  -out:path:all "$OUTDIR" \
  -mute all \
  -unmute protocols.SurfaceDocking \
  "${EXTRA_OPTS[@]}" \
  2>&1 | tee "$LOG"

echo "[OK] Surface docking completed. Results => $OUTDIR"

# 간단한 결과 요약
if [[ -f "$SCOREFILE" ]]; then
  echo ""
  echo "[INFO] Top 5 scores:"
  head -1 "$SCOREFILE"
  tail -n +2 "$SCOREFILE" | sort -k2 -n | head -5
fi