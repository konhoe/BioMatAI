#!/usr/bin/env bash
set -euo pipefail

# Rosetta Surface Docking 스크립트 (수정된 버전)
# 사용법: ./simulation.sh <merged_pdb> <params_dir> [nstruct] [options]

if [[ $# -lt 2 ]]; then
    echo "사용법: $0 <merged_pdb> <params_dir> [nstruct] [options]"
    echo "예시: $0 ../input/merge_pdb/merged_complex.pdb ../params 10"
    exit 1
fi

MERGED_PDB="$1"
PARAMS_DIR="$2"
NSTRUCT="${3:-10}"

# 옵션 파싱
USE_CONSTRAINTS=false
USE_RELAX=false
FORCE_REBUILD=false
DRY_RUN=false

shift 3 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --constraints) USE_CONSTRAINTS=true; shift ;;
        --relax) USE_RELAX=true; shift ;;
        --force) FORCE_REBUILD=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "[WARNING] 알 수 없는 옵션: $1"; shift ;;
    esac
done

# 환경 설정
ROSETTA_HOME="${ROSETTA_HOME:-/Users/junyoung/Desktop/BioMatAI/rosetta/rosetta.binary.m1.release-371/main}"
SCRIPT_DIR="$(cd "$(dirname "$0")"; pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.."; pwd)"

# 파일 경로 절대화 (수정됨)
if [[ "$MERGED_PDB" =~ ^/ ]]; then
    # 이미 절대경로
    :
else
    # 상대경로를 절대경로로 변환
    MERGED_PDB="$SCRIPT_DIR/$MERGED_PDB"
    MERGED_PDB="$(cd "$(dirname "$MERGED_PDB")" && pwd)/$(basename "$MERGED_PDB")"
fi

if [[ "$PARAMS_DIR" =~ ^/ ]]; then
    # 이미 절대경로
    :
else
    # 상대경로를 절대경로로 변환
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
echo "[INFO] 입력 파일 확인 중..."

if [[ ! -f "$MERGED_PDB" ]]; then
    echo "[ERROR] 병합된 PDB 파일이 없습니다: $MERGED_PDB"
    exit 1
fi

if [[ ! -d "$PARAMS_DIR" ]]; then
    echo "[ERROR] Params 디렉토리가 없습니다: $PARAMS_DIR"
    exit 1
fi

# Params 파일 확인
PARAMS_FILES=($(ls "$PARAMS_DIR"/*.params 2>/dev/null || true))
if [[ ${#PARAMS_FILES[@]} -eq 0 ]]; then
    echo "[ERROR] Params 파일이 없습니다: $PARAMS_DIR/*.params"
    exit 1
fi

echo "[OK] 병합된 PDB 파일 확인: $(basename "$MERGED_PDB")"
echo "[OK] Params 파일들 확인:"
for params_file in "${PARAMS_FILES[@]}"; do
    echo "     - $(basename "$params_file")"
done

# 실험 디렉토리 생성
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
EXP_NAME="docking_$(basename "$MERGED_PDB" .pdb)_${TIMESTAMP}"
WORK_DIR="$ROOT_DIR/experiments/$EXP_NAME"

if [[ -d "$WORK_DIR" ]] && [[ "$FORCE_REBUILD" == "true" ]]; then
    echo "[INFO] 기존 실험 디렉토리 삭제 중..."
    rm -rf "$WORK_DIR"
fi

mkdir -p "$WORK_DIR"/{input,output,logs}
cd "$WORK_DIR"

echo "[INFO] 작업 디렉토리 설정: $WORK_DIR"

# 입력 파일들 복사
echo ""
echo "[STEP 1] 입력 파일 준비..."

cp "$MERGED_PDB" "input/complex.pdb"
echo "[OK] PDB 파일 복사 완료"

for params_file in "${PARAMS_FILES[@]}"; do
    cp "$params_file" "input/"
done
PARAMS_BASENAMES=($(for f in "${PARAMS_FILES[@]}"; do basename "$f"; done))
echo "[OK] Params 파일들 복사 완료"

# 제약조건 파일 생성 (옵션)
CONSTRAINTS_FILE=""
if [[ "$USE_CONSTRAINTS" == "true" ]]; then
    echo ""
    echo "[STEP 2] 제약조건 설정..."
    
    CONSTRAINTS_FILE="input/surface_constraints.cst"
    cat > "$CONSTRAINTS_FILE" << 'EOF'
# Ti-protein interaction constraints
AtomPair OD1 50 TI 200 HARMONIC 2.0 0.3
AtomPair NE2 75 TI 201 HARMONIC 2.1 0.3
EOF
    
    echo "[OK] 제약조건 파일 생성: $CONSTRAINTS_FILE"
    echo "[WARNING] 제약조건의 잔기 번호를 실제 시스템에 맞게 수정하세요!"
fi

# Rosetta flags 파일 생성
echo ""
echo "[STEP 3] Rosetta 설정 생성..."

FLAGS_FILE="input/flags_docking"

cat > "$FLAGS_FILE" << EOF
# Rosetta Surface Docking flags
-database $ROSETTA_HOME/database
-s input/complex.pdb
-nstruct $NSTRUCT

# Output options
-out:pdb
-out:file:scorefile output/score.sc
-overwrite
-out:path:all output/

# Score function
-score:weights ref2015
-score:patch score12_w_corrections

# Basic docking options
-docking:docking_local_refine
-docking:dock_pert 3 8
-packing:ex1
-packing:ex2aro

# Basic options
-ignore_unrecognized_res
-run:preserve_header
-run:jran $(date +%s)
EOF

# Params 파일들 개별 추가
for params in "${PARAMS_BASENAMES[@]}"; do
    echo "-extra_res_fa input/$params" >> "$FLAGS_FILE"
done

# 제약조건 추가
if [[ "$USE_CONSTRAINTS" == "true" && -f "$CONSTRAINTS_FILE" ]]; then
    cat >> "$FLAGS_FILE" << EOF
-constraints:cst_file input/$(basename "$CONSTRAINTS_FILE")
-constraints:cst_weight 2.0
EOF
fi

# Relax 옵션 추가
if [[ "$USE_RELAX" == "true" ]]; then
    cat >> "$FLAGS_FILE" << EOF
-relax:default_repeats 3
-relax:jump_move true
-relax:dualspace true
EOF
fi

# 병렬 처리
if [[ $NSTRUCT -gt 20 ]]; then
    echo "-multiple_processes_writing_to_one_directory" >> "$FLAGS_FILE"
fi

echo "[OK] 설정 파일 생성: $FLAGS_FILE"

# Rosetta 바이너리 확인
echo ""
echo "[STEP 4] Rosetta 바이너리 확인..."

POSSIBLE_BINS=(
    "$ROSETTA_HOME/source/bin/docking_protocol.macosclangrelease"
    "$ROSETTA_HOME/source/bin/docking_protocol.static.macosclangrelease"
    "$ROSETTA_HOME/source/bin/docking_protocol.gccrelease"
    "$ROSETTA_HOME/source/bin/docking_protocol.linuxgccrelease"
)

BIN=""
for bin_path in "${POSSIBLE_BINS[@]}"; do
    if [[ -f "$bin_path" ]]; then
        BIN="$bin_path"
        break
    fi
done

if [[ -z "$BIN" ]]; then
    echo "[ERROR] Rosetta 도킹 바이너리를 찾을 수 없습니다"
    echo "        확인 경로: $ROSETTA_HOME/source/bin/"
    echo "        가능한 이름들: docking_protocol.*release"
    exit 1
fi

echo "[OK] 바이너리 확인: $(basename "$BIN")"

# Dry-run 체크
if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "========================================"
    echo "DRY-RUN 모드 - 실제 실행하지 않음"
    echo "========================================"
    echo "실행 명령어:"
    echo "cd $WORK_DIR && $BIN @input/flags_docking"
    exit 0
fi

# Rosetta 실행
echo ""
echo "========================================"
echo "Rosetta 도킹 실행 시작"
echo "========================================"
echo "시작 시간: $(date)"
echo "바이너리: $(basename "$BIN")"
echo "예상 소요 시간: $(($NSTRUCT * 3))분"
echo ""

# 실험 root 디렉토리에서 실행
"$BIN" @input/flags_docking 2>&1 | tee logs/docking.log &
ROSETTA_PID=$!

echo "프로세스 ID: $ROSETTA_PID"
echo ""
echo "모니터링:"
echo "  로그 확인: tail -f $WORK_DIR/logs/docking.log"
echo "  결과 확인: ls -la $WORK_DIR/output/"
echo "  중단: kill $ROSETTA_PID"
echo ""

# 진행 상황 모니터링
echo "진행 상황 모니터링 시작..."
while kill -0 $ROSETTA_PID 2>/dev/null; do
    sleep 60
    COMPLETED=$(ls output/*.pdb 2>/dev/null | wc -l | tr -d ' ')
    if [[ $COMPLETED -gt 0 ]]; then
        PROGRESS=$((COMPLETED * 100 / NSTRUCT))
        echo "[$(date +%H:%M:%S)] 진행률: $COMPLETED/$NSTRUCT ($PROGRESS%)"
    fi
done

wait $ROSETTA_PID
EXIT_CODE=$?

# 결과 분석
echo ""
echo "========================================"
echo "Rosetta 도킹 완료"
echo "========================================"
echo "완료 시간: $(date)"
echo "종료 코드: $EXIT_CODE"

if [[ -f "output/score.sc" ]]; then
    TOTAL_PDBS=$(ls output/*.pdb 2>/dev/null | wc -l | tr -d ' ')
    echo ""
    echo "SUCCESS - 도킹 결과 생성 완료!"
    echo "생성된 구조 수: ${TOTAL_PDBS}개"
    
    if [[ -s "output/score.sc" ]]; then
        echo ""
        echo "상위 5개 구조 점수:"
        echo "----------------------------------------"
        tail -n +2 "output/score.sc" | sort -k2 -n | head -5 | \
        awk '{printf "%-25s %8.2f\n", $1, $2}'
        
        BEST_STRUCTURE=$(tail -n +2 "output/score.sc" | sort -k2 -n | head -1 | awk '{print $1}')
        BEST_SCORE=$(tail -n +2 "output/score.sc" | sort -k2 -n | head -1 | awk '{print $2}')
        
        if [[ -n "$BEST_STRUCTURE" ]]; then
            echo ""
            echo "최고 점수 구조: $BEST_STRUCTURE (Score: $BEST_SCORE)"
            if [[ -f "output/$BEST_STRUCTURE.pdb" ]]; then
                cp "output/$BEST_STRUCTURE.pdb" "output/best_structure.pdb"
                echo "최고 구조 저장: output/best_structure.pdb"
            fi
        fi
    fi
else
    echo ""
    echo "ERROR - 결과 파일이 생성되지 않았습니다"
    
    if [[ -f "logs/docking.log" ]]; then
        echo ""
        echo "에러 로그 마지막 20줄:"
        echo "----------------------------------------"
        tail -20 "logs/docking.log"
    fi
fi

# 실험 요약
echo ""
echo "========================================"
echo "도킹 실험 완료"
echo "========================================"
echo "결과 위치: $WORK_DIR"
echo "입력 PDB: $(basename "$MERGED_PDB")"
echo "Params: ${PARAMS_BASENAMES[*]}"

if [[ $EXIT_CODE -eq 0 && -f "output/score.sc" ]]; then
    echo ""
    echo "다음 단계:"
    echo "  1. 최고 구조 확인: pymol $WORK_DIR/output/best_structure.pdb"
    echo "  2. 점수 분석: sort -k2 -n $WORK_DIR/output/score.sc"
else
    echo ""
    echo "문제 해결:"
    echo "  1. 로그 확인: cat $WORK_DIR/logs/docking.log"
    echo "  2. 입력 파일 검증: pymol $WORK_DIR/input/complex.pdb"
fi

echo "========================================"