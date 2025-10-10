#!/usr/bin/env bash
set -euo pipefail

# Rosetta Surface Docking (surface_docking 바이너리)
# 사용법: ./surfdocking.sh <merged_pdb> <params_dir> [nstruct]

if [[ $# -lt 2 ]]; then
    echo "사용법: $0 <merged_pdb> <params_dir> [nstruct]"
    echo "예시: $0 ../input/merge_pdb/merged_complex.pdb ../params 1"
    exit 1
fi

MERGED_PDB="$1"
PARAMS_DIR="$2"
NSTRUCT="${3:-1}"

# 환경 설정
ROSETTA_HOME="${ROSETTA_HOME:-/Users/junyoung/Desktop/BioMatAI/rosetta/rosetta.binary.m1.release-371/main}"
SCRIPT_DIR="$(cd "$(dirname "$0")"; pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.."; pwd)"

# 파일 경로 절대화
if [[ "$MERGED_PDB" =~ ^/ ]]; then
    :
else
    MERGED_PDB="$SCRIPT_DIR/$MERGED_PDB"
    MERGED_PDB="$(cd "$(dirname "$MERGED_PDB")" && pwd)/$(basename "$MERGED_PDB")"
fi

if [[ "$PARAMS_DIR" =~ ^/ ]]; then
    :
else
    PARAMS_DIR="$SCRIPT_DIR/$PARAMS_DIR"
    PARAMS_DIR="$(cd "$PARAMS_DIR" && pwd)"
fi

echo "========================================"
echo "Rosetta Surface Docking"
echo "========================================"
echo "병합된 PDB: $MERGED_PDB"
echo "Params 디렉토리: $PARAMS_DIR"
echo "구조 수: $NSTRUCT"
echo "========================================"

# 입력 파일 확인
if [[ ! -f "$MERGED_PDB" ]]; then
    echo "[ERROR] 병합된 PDB 파일이 없습니다: $MERGED_PDB"
    exit 1
fi

if [[ ! -d "$PARAMS_DIR" ]]; then
    echo "[ERROR] Params 디렉토리가 없습니다: $PARAMS_DIR"
    exit 1
fi

PARAMS_FILES=($(ls "$PARAMS_DIR"/*.params 2>/dev/null || true))
if [[ ${#PARAMS_FILES[@]} -eq 0 ]]; then
    echo "[ERROR] Params 파일이 없습니다: $PARAMS_DIR/*.params"
    exit 1
fi

# Surface vectors 기본 위치(사용자가 미리 둔 경우)
USER_SURFACE_VECTORS="$ROOT_DIR/input/metal/Ti/Ti_surface_vectors.txt"

echo "[OK] 입력 파일 확인 완료"

# 실험 디렉토리 생성
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
EXP_NAME="surfdock_$(basename "$MERGED_PDB" .pdb)_${TIMESTAMP}"
WORK_DIR="$ROOT_DIR/experiments/$EXP_NAME"

mkdir -p "$WORK_DIR"/{input,output,logs}
cd "$WORK_DIR"

# 입력 복사
cp "$MERGED_PDB" "input/complex.pdb"

# surface_vectors: 우선 사용자 파일 사용, 없으면 자동 생성
SURFVECS_PATH="input/surface_vectors.txt"
if [[ -f "$USER_SURFACE_VECTORS" ]]; then
    cp "$USER_SURFACE_VECTORS" "$SURFVECS_PATH"
    echo "[OK] surface_vectors 사용: $SURFVECS_PATH (사용자 제공)"
else
    echo "[INFO] 사용자 surface_vectors 미존재 → 자동 생성 시도"
    # 자동 생성: surface_docking의 generate 플래그 사용
    GEN_BIN="$ROSETTA_HOME/source/bin/surface_docking.static.macosclangrelease"
    if [[ ! -f "$GEN_BIN" ]]; then
        echo "[ERROR] surface_docking 바이너리를 찾을 수 없습니다: $GEN_BIN"
        exit 1
    fi
    # 생성은 현재 워크디렉토리에서 수행
    "$GEN_BIN" -in:file:s input/complex.pdb -in:file:generate_surface_vectors > logs/generate_surface_vectors.log 2>&1 || true
    # 보통 input/complex.pdb 기준으로 complex.surfvec 생성됨
    if [[ -f "complex.surfvec" ]]; then
        mv "complex.surfvec" "$SURFVECS_PATH"
    elif [[ -f "input/complex.surfvec" ]]; then
        mv "input/complex.surfvec" "$SURFVECS_PATH"
    fi
    if [[ -f "$SURFVECS_PATH" ]]; then
        echo "[OK] surface_vectors 자동 생성 완료: $SURFVECS_PATH"
    else
        echo "[ERROR] surface_vectors 생성 실패. 로그 확인: logs/generate_surface_vectors.log"
        exit 1
    fi
fi

# Fragment 파일(선택 사항: centroid 스킵 시 필수 아님)
FRAG3_SRC="$ROOT_DIR/input/protein/albumin/albumin_3mers"
FRAG9_SRC="$ROOT_DIR/input/protein/albumin/albumin_9mers"
FRAG3_DST=""
FRAG9_DST=""

if [[ -f "$FRAG3_SRC" ]]; then
    cp "$FRAG3_SRC" "input/albumin_3mers"
    FRAG3_DST="input/albumin_3mers"
    echo "[OK] 3mer fragment 복사 완료"
else
    echo "[WARN] 3mer fragment 파일이 없습니다(옵션): $FRAG3_SRC"
fi

if [[ -f "$FRAG9_SRC" ]]; then
    cp "$FRAG9_SRC" "input/albumin_9mers"
    FRAG9_DST="input/albumin_9mers"
    echo "[OK] 9mer fragment 복사 완료"
else
    echo "[WARN] 9mer fragment 파일이 없습니다(옵션): $FRAG9_SRC"
fi

# 리간드 params 복사
for params_file in "${PARAMS_FILES[@]}"; do 
    cp "$params_file" "input/"
done
PARAMS_BASENAMES=($(for f in "${PARAMS_FILES[@]}"; do basename "$f"; done))

echo "[OK] 파일 복사 완료"

# Flags 파일 생성
FLAGS_FILE="input/flags"
cat > "$FLAGS_FILE" << EOF
-database $ROSETTA_HOME/database
-s input/complex.pdb
-nstruct $NSTRUCT

# Output
-out:pdb
-out:file:scorefile output/score.sc
-out:path:all output/
-overwrite

# Score
-score:weights ref2015

# Surface Docking
-docking:partners A_S
-in:file:surface_vectors $SURFVECS_PATH

# Low-res(centroid) 단계 스킵 → 바로 full-atom
-docking:low_res_protocol_only false
-docking:dock_mcm_first_cycles 0
-docking:translate 8
-docking:rotate 3

# Packing
-packing:ex1
-packing:ex2aro

# General
-run:preserve_header
-run:jran $(date +%s)
EOF

# optional: fragment가 있으면 연결(없으면 생략)
if [[ -n "$FRAG3_DST" ]]; then
    echo "-in:file:frag3 $FRAG3_DST" >> "$FLAGS_FILE"
fi
if [[ -n "$FRAG9_DST" ]]; then
    echo "-in:file:frag9 $FRAG9_DST" >> "$FLAGS_FILE"
fi

# Full-atom params 추가
for params in "${PARAMS_BASENAMES[@]}"; do
    if [[ ! "$params" =~ _centroid\.params$ ]]; then
        echo "-extra_res_fa input/$params" >> "$FLAGS_FILE"
    fi
done

echo "[OK] 설정 파일 생성 완료: $FLAGS_FILE"

# Surface docking 바이너리
BIN="$ROSETTA_HOME/source/bin/surface_docking.static.macosclangrelease"
if [[ ! -f "$BIN" ]]; then
    echo "[ERROR] surface_docking 바이너리를 찾을 수 없습니다: $BIN"
    exit 1
fi

echo "[OK] 바이너리 확인: $(basename "$BIN")"

# 실행
echo ""
echo "========================================"
echo "Surface Docking 실행 시작"
echo "========================================"
echo "시작 시간: $(date)"

"$BIN" @input/flags 2>&1 | tee logs/surfdock.log &
ROSETTA_PID=$!
echo "프로세스 ID: $ROSETTA_PID"
echo ""

# 대기
wait $ROSETTA_PID
EXIT_CODE=$?

# 결과
echo ""
echo "========================================"
echo "완료 (종료 코드: $EXIT_CODE)"
echo "========================================"

if [[ -f "output/score.sc" ]]; then
    TOTAL_PDBS=$(ls output/*.pdb 2>/dev/null | wc -l | tr -d ' ')
    echo "생성된 구조 수: ${TOTAL_PDBS}개"
    if [[ -s "output/score.sc" ]]; then
        echo "상위 5개 구조:"
        tail -n +2 "output/score.sc" | sort -k2 -n | head -5
    fi
else
    echo "ERROR - 결과 없음"
    echo "로그 확인: tail -50 logs/surfdock.log"
fi

echo "========================================"