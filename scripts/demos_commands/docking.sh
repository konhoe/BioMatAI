#!/usr/bin/env bash
set -euo pipefail

# Metal-Protein Surface Docking 통합 스크립트
# 사용법: ./docking.sh <protein_name> <metal_name> [nstruct] [options]

# 인자 확인
if [[ $# -lt 2 ]]; then
    echo "사용법: $0 <protein_name> <metal_name> [nstruct] [options]"
    echo "예시: $0 albumin TiP2 10"
    echo "      $0 albumin TiP2 100 --constraints --auto-params"
    exit 1
fi

PROTEIN_NAME="$1"
METAL_NAME="$2"
NSTRUCT="${3:-10}"  # 기본값 10

# 추가 옵션 파싱
AUTO_PARAMS=false
USE_CONSTRAINTS=false
FORCE_REBUILD=false
DRY_RUN=false

shift 3 || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --auto-params)
            AUTO_PARAMS=true
            shift
            ;;
        --constraints)
            USE_CONSTRAINTS=true
            shift
            ;;
        --force)
            FORCE_REBUILD=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "[WARNING] 알 수 없는 옵션: $1"
            shift
            ;;
    esac
done

# 환경 설정
ROSETTA_HOME="${ROSETTA_HOME:-/Users/junyoung/Desktop/BioMatAI/rosetta/rosetta.binary.m1.release-371/main}"
SCRIPT_DIR="$(cd "$(dirname "$0")"; pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.."; pwd)"

# 디렉토리 설정
INPUT_DIR="$ROOT_DIR/input"
EXPERIMENTS_DIR="$ROOT_DIR/experiments"
SCRIPTS_DIR="$ROOT_DIR/scripts"

# 실험 이름 및 디렉토리
EXP_NAME="${PROTEIN_NAME}_${METAL_NAME}"
WORK_DIR="$EXPERIMENTS_DIR/$EXP_NAME"

echo "========================================"
echo "Metal-Protein Surface Docking"
echo "========================================"
echo "단백질: $PROTEIN_NAME"
echo "금속/표면: $METAL_NAME"
echo "구조 수: $NSTRUCT"
echo "작업 디렉토리: $WORK_DIR"
echo "자동 params: $AUTO_PARAMS"
echo "제약조건 사용: $USE_CONSTRAINTS"
echo "========================================"

# 입력 파일 경로
PROTEIN_FASTA="$INPUT_DIR/protein/$PROTEIN_NAME/${PROTEIN_NAME}.fasta"
PROTEIN_PDB="$INPUT_DIR/protein/$PROTEIN_NAME/${PROTEIN_NAME}.pdb"

# 금속 파일 검색 (Ti 폴더에서 TiP2.pdb 찾기)
METAL_PDB="$INPUT_DIR/metal/Ti/$METAL_NAME.pdb"

echo "[INFO] 입력 파일 확인 중..."

# 단백질 파일들 확인
if [[ ! -f "$PROTEIN_FASTA" ]]; then
    echo "[ERROR] 단백질 FASTA 파일이 없습니다: $PROTEIN_FASTA"
    exit 1
fi

if [[ ! -f "$PROTEIN_PDB" ]]; then
    echo "[ERROR] 단백질 PDB 파일이 없습니다: $PROTEIN_PDB"
    exit 1
fi

# 금속 파일 확인
if [[ ! -f "$METAL_PDB" ]]; then
    echo "[ERROR] 금속/표면 PDB 파일을 찾을 수 없습니다: $METAL_PDB"
    echo "        파일이 다음 위치에 있는지 확인하세요:"
    echo "        $METAL_PDB"
    exit 1
fi

echo "[INFO] 금속 파일 발견: $METAL_PDB"
echo "[OK] 모든 입력 파일 확인 완료"

# 실험 디렉토리 생성
if [[ -d "$WORK_DIR" ]] && [[ "$FORCE_REBUILD" == "true" ]]; then
    echo "[INFO] 기존 실험 디렉토리 삭제 중..."
    rm -rf "$WORK_DIR"
fi

mkdir -p "$WORK_DIR"/{input,output,logs,analysis,params,surfaces}
cd "$WORK_DIR"

echo "[INFO] 작업 디렉토리 설정 완료"

# 1. 금속 params 파일 생성/확인
echo ""
echo "[STEP 1] 금속 Params 파일 처리..."

if [[ "$AUTO_PARAMS" == "true" ]]; then
    echo "[INFO] 자동으로 금속 params 생성 중..."
    
    # 금속명 매핑 (파일명 → 실제 금속 원소)
    ACTUAL_METAL=""
    case "$METAL_NAME" in
        Ti|TiO2|TiP2)
            ACTUAL_METAL="TiP2"  # TiP2 직접 지원
            ;;
        Ca|CaCO3|Calcite)
            ACTUAL_METAL="Ca"
            ;;
        Zn|ZnO)
            ACTUAL_METAL="Zn"
            ;;
        Mg|MgO)
            ACTUAL_METAL="Mg"
            ;;
        Cu|CuO)
            ACTUAL_METAL="Cu"
            ;;
        Fe|FeO|Fe2O3)
            ACTUAL_METAL="Fe"
            ;;
        Al|Al2O3)
            ACTUAL_METAL="Al"
            ;;
        Ni|NiO)
            ACTUAL_METAL="Ni"
            ;;
        *)
            ACTUAL_METAL="Ti"  # 기본값
            echo "[WARNING] 알 수 없는 금속 '$METAL_NAME', Ti로 설정"
            ;;
    esac
    
    echo "[INFO] $METAL_NAME → $ACTUAL_METAL 원소로 params 생성"
    
    python "$SCRIPTS_DIR/metal_residue.py" \
        --metal "$ACTUAL_METAL" \
        --anion O \
        --output params/
    
    PARAMS_FILES=$(ls params/*.params 2>/dev/null | xargs -n1 basename | tr '\n' ' ' || echo "")
    
    # params 파일들을 input 디렉토리로 복사 (Rosetta가 찾을 수 있도록)
    if [[ -n "$PARAMS_FILES" ]]; then
        echo "[INFO] Params 파일들을 input 디렉토리로 복사 중..."
        cp params/*.params input/
        echo "       복사 완료: $PARAMS_FILES"
    fi
else
    # 기존 params 파일 확인
    PARAMS_FILES=""
    if ls "$ROOT_DIR/params/"*.params >/dev/null 2>&1; then
        cp "$ROOT_DIR/params/"*.params params/
        PARAMS_FILES=$(ls params/*.params 2>/dev/null | xargs -n1 basename | tr '\n' ' ' || echo "")
        echo "[INFO] 기존 params 파일 복사 완료"
    else
        echo "[WARNING] Params 파일이 없습니다. --auto-params 옵션을 사용하거나 수동으로 생성하세요."
    fi
fi

echo "       Params 파일: $PARAMS_FILES"

# 2. 표면 벡터 파일 생성
echo ""
echo "[STEP 2] 표면 벡터 파일 생성..."

# 금속별 기본 표면 설정
case "$METAL_NAME" in
    Ti|TiO2|TiP2)
        SURFACE_TYPE="TiO2"
        CRYSTAL_PHASE="rutile"
        SURFACE_FACE="110"
        ;;
    Ca|CaCO3)
        SURFACE_TYPE="CaCO3"
        CRYSTAL_PHASE="calcite"
        SURFACE_FACE="104"
        ;;
    HAP|Hydroxyapatite)
        SURFACE_TYPE="HAP"
        CRYSTAL_PHASE="hexagonal"
        SURFACE_FACE="001"
        ;;
    *)
        # 기본값 (TiO2)
        SURFACE_TYPE="TiO2"
        CRYSTAL_PHASE="rutile"
        SURFACE_FACE="110"
        echo "[WARNING] 알 수 없는 금속 '$METAL_NAME', TiO2 rutile (110) 사용"
        ;;
esac

python "$SCRIPTS_DIR/metal_surf.py" \
    --surface "$SURFACE_TYPE" \
    --phase "$CRYSTAL_PHASE" \
    --face "$SURFACE_FACE" \
    --output surfaces/

SURF_FILE="surfaces/${SURFACE_TYPE}_${CRYSTAL_PHASE}_${SURFACE_FACE}.surf"
if [[ -f "$SURF_FILE" ]]; then
    cp "$SURF_FILE" "input/${METAL_NAME}.surf"
    echo "[OK] 표면 벡터 파일 준비 완료"
else
    echo "[ERROR] 표면 벡터 파일 생성 실패"
    exit 1
fi

# 3. PDB 파일 병합
echo ""
echo "[STEP 3] PDB 파일 병합..."

MERGED_PDB="input/${EXP_NAME}_merged.pdb"

if [[ "$DRY_RUN" == "false" ]]; then
    python "$SCRIPTS_DIR/merge_pdb.py" \
        --protein-file "$PROTEIN_PDB" \
        --surface-file "$METAL_PDB" \
        --output "$MERGED_PDB" \
        --protein-chain P \
        --surface-chain S \
        --gap 12.0
    
    if [[ ! -f "$MERGED_PDB" ]]; then
        echo "[ERROR] PDB 병합 실패"
        exit 1
    fi
else
    echo "[DRY-RUN] PDB 병합 건너뛰기"
fi

echo "[OK] PDB 병합 완료: $MERGED_PDB"

# 4. Fragment 파일 확인
echo ""
echo "[STEP 4] Fragment 파일 확인..."

FRAGMENT_9MER="input/${PROTEIN_NAME}_9mers"
FRAGMENT_3MER="input/${PROTEIN_NAME}_3mers"

if [[ ! -f "$FRAGMENT_9MER" ]] || [[ ! -f "$FRAGMENT_3MER" ]]; then
    echo ""
    echo "=========================================="
    echo "FRAGMENT 파일이 필요합니다!"
    echo "=========================================="
    echo ""
    echo "다음 중 한 가지 방법을 선택하세요:"
    echo ""
    echo "1. Robetta 서버 사용 (권장):"
    echo "   - http://robetta.bakerlab.org/ 접속"
    echo "   - $PROTEIN_FASTA 파일 업로드"
    echo "   - Fragment files 다운로드"
    echo "   - ${PROTEIN_NAME}_9mers, ${PROTEIN_NAME}_3mers 파일명으로 저장"
    echo "   - $WORK_DIR/input/ 디렉토리에 복사"
    echo ""
    echo "2. 수동 생성 (테스트용):"
    
    # 시퀀스 길이 계산
    SEQUENCE=$(grep -v "^>" "$PROTEIN_FASTA" 2>/dev/null | tr -d '\n' || echo "")
    SEQ_LEN=${#SEQUENCE}
    
    if [[ $SEQ_LEN -gt 0 ]]; then
        echo "   시퀀스 길이: $SEQ_LEN"
        echo "   필요 positions: 9mer($((SEQ_LEN - 8))개), 3mer($((SEQ_LEN - 2))개)"
        echo ""
        echo "   cd $WORK_DIR/input"
        echo "   # 간단한 더미 fragment 생성 (테스트용)"
        echo "   for pos in \$(seq 1 $((SEQ_LEN - 8))); do"
        echo "       echo ' position:         '\$pos' neighbors:       200' >> ${PROTEIN_NAME}_9mers"
        echo "       for i in \$(seq 0 8); do"
        echo "           echo ' 1ubq A  '\$((26 + i))' A V  -64.5  150.0 -178.0  -0.9   4.5   17.5 3   0.000 P  1 F  1' >> ${PROTEIN_NAME}_9mers"
        echo "       done"
        echo "       echo '' >> ${PROTEIN_NAME}_9mers"
        echo "   done"
        echo ""
        echo "   for pos in \$(seq 1 $((SEQ_LEN - 2))); do"
        echo "       echo ' position:         '\$pos' neighbors:       200' >> ${PROTEIN_NAME}_3mers"
        echo "       for i in \$(seq 0 2); do"
        echo "           echo ' 1ubq A  '\$((26 + i))' A V  -64.5  150.0 -178.0  -0.9   4.5   17.5 3   0.000 P  1 F  1' >> ${PROTEIN_NAME}_3mers"
        echo "       done"
        echo "       echo '' >> ${PROTEIN_NAME}_3mers"
        echo "   done"
    fi
    
    echo ""
    echo "Fragment 파일 준비 후 다시 실행하세요:"
    echo "$0 $PROTEIN_NAME $METAL_NAME $NSTRUCT"
    exit 1
fi

FRAG_9_COUNT=$(grep "position:" "$FRAGMENT_9MER" | wc -l | tr -d ' ')
FRAG_3_COUNT=$(grep "position:" "$FRAGMENT_3MER" | wc -l | tr -d ' ')

echo "[OK] Fragment 파일 확인 완료"
echo "     9mer: $FRAG_9_COUNT positions"
echo "     3mer: $FRAG_3_COUNT positions"

# 5. 제약조건 파일 생성
echo ""
echo "[STEP 5] 제약조건 설정..."

CONSTRAINTS_FILE=""
if [[ "$USE_CONSTRAINTS" == "true" ]]; then
    CONSTRAINTS_FILE="input/${METAL_NAME}_constraints.cst"
    
    # 금속별 제약조건 생성
    case "$METAL_NAME" in
        Ti|TiO2|TiP2)
            cat > "$CONSTRAINTS_FILE" << 'EOF'
# Ti4+ coordination constraints
# Ti-O coordination (1.9-2.1 Å)
AtomPair OD1 150 TI 400 HARMONIC 2.0 0.1
AtomPair OE1 200 TI 401 HARMONIC 2.0 0.1
# Ti-N coordination (His, 2.0-2.2 Å)
AtomPair NE2 80 TI 402 HARMONIC 2.1 0.1
EOF
            ;;
        Ca|CaCO3)
            cat > "$CONSTRAINTS_FILE" << 'EOF'
# Ca2+ coordination constraints
# Ca-O coordination (2.3-2.5 Å)
AtomPair OD1 120 CA 400 HARMONIC 2.4 0.15
AtomPair OE1 145 CA 400 HARMONIC 2.4 0.15
# Ca-N coordination (2.4-2.6 Å)
AtomPair NE2 67 CA 401 HARMONIC 2.5 0.15
EOF
            ;;
        *)
            cat > "$CONSTRAINTS_FILE" << 'EOF'
# Generic metal coordination constraints
# Adjust residue numbers and distances as needed
AtomPair OD1 100 X 400 HARMONIC 2.2 0.2
AtomPair NE2 50 X 401 HARMONIC 2.3 0.2
EOF
            ;;
    esac
    
    echo "[OK] 제약조건 파일 생성: $CONSTRAINTS_FILE"
else
    echo "[INFO] 제약조건 미사용"
fi

# 6. RosettaSurface flags 파일 생성
echo ""
echo "[STEP 6] RosettaSurface 설정 생성..."

FLAGS_FILE="input/flags_${EXP_NAME}"

cat > "$FLAGS_FILE" << EOF
# RosettaSurface flags for $EXP_NAME
# Generated by docking.sh

# Input files
-database $ROSETTA_HOME/database
-s ${EXP_NAME}_merged.pdb
-in:file:surface_vectors ${METAL_NAME}.surf
-in:file:frag9 ${PROTEIN_NAME}_9mers
-in:file:frag3 ${PROTEIN_NAME}_3mers

# Surface docking options
-include_surfaces
-nstruct $NSTRUCT
-out:pdb
-overwrite

# Score function (논문 권장)
-score:weights score12
-score:patch score12_w_corrections

# Basic options
-ignore_unrecognized_res
-run:preserve_header
EOF

# Params 파일 추가
if [[ -n "$PARAMS_FILES" ]]; then
    echo "-in:file:extra_res_fa $PARAMS_FILES" >> "$FLAGS_FILE"
fi

# 제약조건 추가
if [[ "$USE_CONSTRAINTS" == "true" && -f "$CONSTRAINTS_FILE" ]]; then
    echo "-constraints:cst_file $(basename "$CONSTRAINTS_FILE")" >> "$FLAGS_FILE"
    echo "-constraints:cst_weight 5.0" >> "$FLAGS_FILE"
fi

# 병렬 처리 설정
if [[ $NSTRUCT -gt 50 ]]; then
    echo "-multiple_processes_writing_to_one_directory" >> "$FLAGS_FILE"
fi

echo "[OK] 설정 파일 생성: $FLAGS_FILE"

# 7. Rosetta 바이너리 확인
echo ""
echo "[STEP 7] Rosetta 바이너리 확인..."

# 가능한 바이너리 경로들 (우선순위대로)
POSSIBLE_BINS=(
    "$ROSETTA_HOME/source/bin/surface_docking.macosclangrelease"
    "$ROSETTA_HOME/source/bin/surface_docking.gccrelease"
    "$ROSETTA_HOME/source/bin/surface_docking.static.macosclangrelease"
    "$ROSETTA_HOME/source/bin/surface_docking.linuxgccrelease"
)

BIN=""
for bin_path in "${POSSIBLE_BINS[@]}"; do
    if [[ -f "$bin_path" ]]; then
        BIN="$bin_path"
        break
    fi
done

if [[ -z "$BIN" ]]; then
    echo "[ERROR] RosettaSurface 바이너리를 찾을 수 없습니다"
    echo "        확인 경로: $ROSETTA_HOME/source/bin/"
    echo "        가능한 이름들: surface_docking.*release"
    exit 1
fi

echo "[OK] 바이너리 확인: $BIN"

# 8. Dry-run 체크
if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "========================================"
    echo "DRY-RUN 모드 - 실제 실행하지 않음"
    echo "========================================"
    echo "준비 완료된 파일들:"
    echo "  - PDB: $MERGED_PDB"
    echo "  - 표면 벡터: input/${METAL_NAME}.surf"
    echo "  - Fragment: $FRAGMENT_9MER, $FRAGMENT_3MER"
    echo "  - Flags: $FLAGS_FILE"
    if [[ -n "$CONSTRAINTS_FILE" ]]; then
        echo "  - 제약조건: $CONSTRAINTS_FILE"
    fi
    echo ""
    echo "실행 명령어:"
    echo "cd $WORK_DIR/input && $BIN @flags_${EXP_NAME}"
    exit 0
fi

# 9. RosettaSurface 실행
echo ""
echo "========================================"
echo "RosettaSurface 실행 시작"
echo "========================================"
echo "시작 시간: $(date)"
echo "바이너리: $BIN"
echo "예상 소요 시간: $(($NSTRUCT * 5))분 (구조당 ~5분)"
echo ""

cd input

# 실행
"$BIN" @"flags_${EXP_NAME}" 2>&1 | tee ../logs/surface_docking.log &

ROSETTA_PID=$!
echo "프로세스 ID: $ROSETTA_PID"
echo ""
echo "실행 중 모니터링:"
echo "  로그 확인: tail -f $WORK_DIR/logs/surface_docking.log"
echo "  진행 상황: ls -la $WORK_DIR/output/"
echo "  중단: kill $ROSETTA_PID"
echo ""

# 대기
wait $ROSETTA_PID
EXIT_CODE=$?

cd ..

# 10. 결과 분석
echo ""
echo "========================================"
echo "RosettaSurface 실행 완료"
echo "========================================"
echo "완료 시간: $(date)"
echo "종료 코드: $EXIT_CODE"

# 결과 파일 확인
SCORE_FILE=""
if [[ -f "output/score.sc" ]]; then
    SCORE_FILE="output/score.sc"
elif [[ -f "output/score.fasc" ]]; then
    SCORE_FILE="output/score.fasc"
fi

if [[ -n "$SCORE_FILE" ]]; then
    # 결과 통계
    SOL_COUNT=$(ls output/*_sol_*.pdb 2>/dev/null | wc -l | tr -d ' ')
    ADS_COUNT=$(ls output/*_ads_*.pdb 2>/dev/null | wc -l | tr -d ' ')
    FINAL_COUNT=$(ls output/*_final_*.pdb 2>/dev/null | wc -l | tr -d ' ')
    TOTAL_PDB=$(ls output/*.pdb 2>/dev/null | wc -l | tr -d ' ')
    
    echo ""
    echo "✅ SUCCESS - 결과 생성 완료!"
    echo ""
    echo "생성된 구조들:"
    echo "  - Solution state: ${SOL_COUNT}개"
    echo "  - Adsorbed state: ${ADS_COUNT}개"
    echo "  - Final scored: ${FINAL_COUNT}개"
    echo "  - 총 PDB 파일: ${TOTAL_PDB}개"
    
    # 점수 분석
    if [[ -s "$SCORE_FILE" ]]; then
        echo ""
        echo "상위 5개 구조 점수:"
        echo "----------------------------------------"
        head -6 "$SCORE_FILE" | tail -5
        
        # 최고 점수 구조
        BEST_STRUCTURE=$(tail -n +2 "$SCORE_FILE" | sort -k2 -n | head -1 | awk '{print $1}')
        if [[ -n "$BEST_STRUCTURE" ]]; then
            echo ""
            echo "최고 점수 구조: $BEST_STRUCTURE"
        fi
    fi
    
else
    echo ""
    echo "❌ ERROR - 결과가 생성되지 않았습니다"
    echo ""
    echo "문제 진단을 위해 로그를 확인하세요:"
    echo "tail -50 logs/surface_docking.log"
    
    if [[ -f "logs/surface_docking.log" ]]; then
        echo ""
        echo "로그 마지막 20줄:"
        echo "----------------------------------------"
        tail -20 "logs/surface_docking.log"
    fi
fi

echo ""
echo "========================================"
echo "실험 요약"
echo "========================================"
echo "단백질: $PROTEIN_NAME ($(grep -v '^>' "$PROTEIN_FASTA" | tr -d '\n' | wc -c)개 잔기)"
echo "표면: $METAL_NAME ($SURFACE_TYPE $CRYSTAL_PHASE $SURFACE_FACE)"
echo "Fragment: 9mer($FRAG_9_COUNT), 3mer($FRAG_3_COUNT)"
echo "구조 수: $NSTRUCT"
echo "제약조건: $(if [[ "$USE_CONSTRAINTS" == "true" ]]; then echo "사용"; else echo "미사용"; fi)"
echo "결과 위치: $WORK_DIR"
echo ""
echo "다음 단계:"
echo "  1. PyMOL로 구조 시각화: pymol output/best_structure.pdb"
echo "  2. 에너지 분석: analysis/score_analysis.py"
echo "  3. 표면 접촉 분석: analysis/contact_analysis.py"