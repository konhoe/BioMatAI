#!/usr/bin/env bash
set -euo pipefail

# SurfRosetta 도킹 데모 스크립트 (Fragment는 수동 생성)
# 사용법: ./docking_demo.sh <protein_name> <surface_name> [nstruct]

# 인자 확인
if [[ $# -lt 2 ]]; then
    echo "사용법: $0 <protein_name> <surface_name> [nstruct]"
    echo "예시: $0 albumin calcite 1"
    exit 1
fi

PROTEIN_NAME="$1"
SURFACE_NAME="$2"
NSTRUCT="${3:-1}"  # 기본값 1

# 환경 설정
ROSETTA_HOME="${ROSETTA_HOME:-/Users/junyoung/Desktop/BioMatAI/rosetta/rosetta.binary.m1.release-371/main}"
SCRIPT_DIR="$(cd "$(dirname "$0")"; pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.."; pwd)"

INPUT_PROTEINS="$ROOT_DIR/input/proteins"
INPUT_SURFACES="$ROOT_DIR/input/surfaces"
EXPERIMENTS_DIR="$ROOT_DIR/experiments"

# 실험 디렉토리 설정
EXP_NAME="${PROTEIN_NAME}_${SURFACE_NAME}"
WORK_DIR="$EXPERIMENTS_DIR/$EXP_NAME"

echo "[INFO] SurfRosetta 도킹 데모 시작"
echo "       단백질: $PROTEIN_NAME"
echo "       표면: $SURFACE_NAME"
echo "       구조 수: $NSTRUCT"
echo "       작업 디렉토리: $WORK_DIR"

# 입력 파일 확인
PROTEIN_FASTA="$INPUT_PROTEINS/${PROTEIN_NAME}.fasta"
PROTEIN_PDB="$INPUT_PROTEINS/${PROTEIN_NAME}.pdb"
SURFACE_PDB="$INPUT_SURFACES/${SURFACE_NAME}.pdb"
SURFACE_VECTORS="$INPUT_SURFACES/${SURFACE_NAME}.surf"

echo "[INFO] 입력 파일 확인 중..."

if [[ ! -f "$PROTEIN_FASTA" ]]; then
    echo "[ERROR] 단백질 FASTA 파일을 찾을 수 없습니다: $PROTEIN_FASTA"
    exit 1
fi

if [[ ! -f "$SURFACE_PDB" ]]; then
    echo "[ERROR] 표면 PDB 파일을 찾을 수 없습니다: $SURFACE_PDB"
    exit 1
fi

if [[ ! -f "$SURFACE_VECTORS" ]]; then
    echo "[WARNING] 표면 벡터 파일을 찾을 수 없습니다. 기본값을 생성합니다."
    mkdir -p "$(dirname "$SURFACE_VECTORS")"
    echo "18.671 -38.353   9.571
17.705 -36.371   5.096
12.153 -43.099   8.876" > "$SURFACE_VECTORS"
    echo "[OK] 기본 표면 벡터 파일 생성: $SURFACE_VECTORS"
fi

echo "[OK] 모든 입력 파일 확인 완료"

# 실험 디렉토리 생성 (강화된 권한 설정)
mkdir -p "$WORK_DIR"/{input,output,logs,analysis}
chmod 755 "$WORK_DIR"
chmod 777 "$WORK_DIR/output"  # 출력 디렉토리는 모든 권한
chmod 755 "$WORK_DIR/input"
chmod 755 "$WORK_DIR/logs"
cd "$WORK_DIR"

echo "[INFO] 디렉토리 권한 설정 완료"
echo "       output 권한: $(ls -ld output | awk '{print $1}')"

echo "[INFO] 단백질 시퀀스 읽기..."

# 단백질 시퀀스 추출
SEQUENCE=$(grep -v "^>" "$PROTEIN_FASTA" | tr -d '\n')
SEQUENCE_LENGTH=${#SEQUENCE}

echo "       FASTA 시퀀스 길이: $SEQUENCE_LENGTH"
echo "       시퀀스: ${SEQUENCE:0:50}..."

# 표면 벡터 복사
cp "$SURFACE_VECTORS" input/${SURFACE_NAME}.surf
echo "[OK] 표면 벡터 파일 복사 완료"

# PDB 파일 병합 또는 복사
echo "[INFO] PDB 파일 준비 중..."

if [[ -f "$PROTEIN_PDB" ]]; then
    # 단백질 PDB가 있으면 표면과 병합 (make_merged_pdb.py 사용)
    echo "[INFO] 단백질과 표면 PDB 병합 중..."
    
    MERGED_PDB="input/${EXP_NAME}_merged.pdb"
    python "$SCRIPT_DIR/make_merged_pdb.py" -p "$PROTEIN_PDB" -s "$SURFACE_PDB" -o "$MERGED_PDB" --order surface-protein
    
    if [[ ! -f "$MERGED_PDB" ]]; then
        echo "[ERROR] PDB 병합 실패"
        exit 1
    fi
else
    # 단백질 PDB가 없으면 표면만 사용 (de novo folding)
    echo "[INFO] 표면 PDB만 사용 (de novo folding)"
    MERGED_PDB="input/${EXP_NAME}_surface.pdb"
    python "$SCRIPT_DIR/make_merged_pdb.py" -s "$SURFACE_PDB" -o "$MERGED_PDB"
fi

echo "[OK] PDB 파일 준비 완료: $MERGED_PDB"

# Fragment 파일 존재 확인
echo "[INFO] Fragment 파일 확인 중..."

FRAGMENT_9MER="input/${PROTEIN_NAME}_9mers"
FRAGMENT_3MER="input/${PROTEIN_NAME}_3mers"

if [[ ! -f "$FRAGMENT_9MER" ]] || [[ ! -f "$FRAGMENT_3MER" ]]; then
    echo "[WARNING] Fragment 파일이 없습니다. 수동으로 생성하세요:"
    echo ""
    echo "# PDB 잔기 범위 확인"
    FIRST_RES=$(grep "^ATOM" "$MERGED_PDB" | grep " A " | awk '{print $6}' | sort -n | head -1 2>/dev/null || echo 1)
    LAST_RES=$(grep "^ATOM" "$MERGED_PDB" | grep " A " | awk '{print $6}' | sort -n | tail -1 2>/dev/null || echo 0)
    ACTUAL_COUNT=$((LAST_RES - FIRST_RES + 1))
    
    echo "잔기 범위: $FIRST_RES-$LAST_RES (총 $ACTUAL_COUNT 개)"
    echo "9mer positions 필요: $((ACTUAL_COUNT - 8))개"
    echo "3mer positions 필요: $((ACTUAL_COUNT - 2))개"
    echo ""
    echo "cd $WORK_DIR/input"
    echo ""
    echo "# 9mer fragment 생성"
    echo "> ${PROTEIN_NAME}_9mers"
    echo "for pos in \$(seq 1 $((ACTUAL_COUNT - 8))); do"
    echo "    echo \" position:            \$pos neighbors:          200\" >> ${PROTEIN_NAME}_9mers"
    echo "    echo \"\" >> ${PROTEIN_NAME}_9mers"
    echo "    for i in \$(seq 0 8); do"
    echo "        echo \" 2csb A   \$((182 + i)) A L  -74.810  164.036  180.795   -0.505    6.791    25.816 3     0.000 P  1 F  1\" >> ${PROTEIN_NAME}_9mers"
    echo "    done"
    echo "    echo \"\" >> ${PROTEIN_NAME}_9mers"
    echo "done"
    echo ""
    echo "# 3mer fragment 생성"
    echo "> ${PROTEIN_NAME}_3mers"
    echo "for pos in \$(seq 1 $((ACTUAL_COUNT - 2))); do"
    echo "    echo \" position:            \$pos neighbors:          200\" >> ${PROTEIN_NAME}_3mers"
    echo "    echo \"\" >> ${PROTEIN_NAME}_3mers"
    echo "    for i in \$(seq 0 2); do"
    echo "        echo \" 2q52 A   \$((210 + i)) A L  -64.109  141.950 -176.586   -0.911    4.490    17.477 3     0.000 P  1 F  1\" >> ${PROTEIN_NAME}_3mers"
    echo "    done"
    echo "    echo \"\" >> ${PROTEIN_NAME}_3mers"
    echo "done"
    echo ""
    echo "Fragment 생성 후 다시 실행하세요: $0 $PROTEIN_NAME $SURFACE_NAME $NSTRUCT"
    exit 1
fi

# Fragment 파일 확인
FRAG_9_COUNT=$(grep "position:" "$FRAGMENT_9MER" | wc -l | tr -d ' ')
FRAG_3_COUNT=$(grep "position:" "$FRAGMENT_3MER" | wc -l | tr -d ' ')

echo "[OK] Fragment 파일 확인 완료"
echo "     9mer: $FRAG_9_COUNT positions"
echo "     3mer: $FRAG_3_COUNT positions"

# flags 파일 생성
echo "[INFO] 설정 파일 생성 중..."

cat > input/flags_${EXP_NAME} << EOF
-s albumin_calcite_merged.pdb
-include_surfaces
-overwrite
-nstruct 1
-out:pdb
-in:file:frag9 albumin_9mers
-in:file:frag3 albumin_3mers
-in:file:surface_vectors calcite.surf
-ignore_unrecognized_res
EOF

echo "[OK] 설정 파일 생성 완료"

# Rosetta 바이너리 확인
BIN="$ROSETTA_HOME/source/bin/surface_docking.static.macosclangrelease"
if [[ ! -f "$BIN" ]]; then
    BIN="$ROSETTA_HOME/source/bin/surface_docking.macosclangrelease"
fi

if [[ ! -f "$BIN" ]]; then
    echo "[ERROR] SurfRosetta 바이너리를 찾을 수 없습니다"
    echo "        확인 경로: $ROSETTA_HOME/source/bin/"
    exit 1
fi

echo "[INFO] SurfRosetta 실행 시작..."
echo "       바이너리: $BIN"
echo "       시작 시간: $(date)"

# 실행 직전 출력 디렉토리 재확인 및 생성
OUTPUT_DIR="$(pwd)/../output"
mkdir -p "$OUTPUT_DIR"
chmod 777 "$OUTPUT_DIR"
echo "       출력 디렉토리: $OUTPUT_DIR (권한: $(ls -ld "$OUTPUT_DIR" | awk '{print $1}'))"

# SurfRosetta 실행
cd input
"$BIN" @flags_${EXP_NAME} 2>&1 | tee ../logs/surfrosetta.log &

# 프로세스 ID 저장
ROSETTA_PID=$!
echo "       프로세스 ID: $ROSETTA_PID"

# 실행 중 모니터링
echo ""
echo "[INFO] 실행 중 모니터링 명령어:"
echo "       로그 확인: tail -f $WORK_DIR/logs/surfrosetta.log"
echo "       프로세스 확인: ps aux | grep $ROSETTA_PID"
echo "       진행 상황: ls -la $WORK_DIR/output/"
echo "       중단: kill $ROSETTA_PID"

# 백그라운드에서 실행되므로 대기
wait $ROSETTA_PID
EXIT_CODE=$?

cd ..

# 결과 확인
echo ""
echo "[INFO] SurfRosetta 실행 완료"
echo "       완료 시간: $(date)"
echo "       종료 코드: $EXIT_CODE"
echo "       작업 디렉토리: $WORK_DIR"
echo "       로그 파일: logs/surfrosetta.log"

if [[ -f "output/score.sc" ]]; then
    RESULT_COUNT=$(ls output/*.pdb 2>/dev/null | wc -l | tr -d ' ')
    echo "[SUCCESS] 결과 생성 완료!"
    echo "          점수 파일: output/score.sc"
    echo "          PDB 파일: ${RESULT_COUNT}개"
    
    if [[ -s "output/score.sc" ]] && [[ $RESULT_COUNT -gt 0 ]]; then
        echo ""
        echo "[INFO] 상위 점수들:"
        head -10 "output/score.sc"
        echo ""
        echo "[INFO] 생성된 PDB 파일들:"
        ls -la output/*.pdb | head -5
    fi
else
    echo "[ERROR] 결과가 생성되지 않았습니다."
    echo "        로그 확인: tail -20 logs/surfrosetta.log"
    
    if [[ -f "logs/surfrosetta.log" ]]; then
        echo ""
        echo "[INFO] 로그 마지막 20줄:"
        tail -20 "logs/surfrosetta.log"
    fi
fi

echo ""
echo "[INFO] 실험 요약:"
echo "       단백질: $PROTEIN_NAME ($SEQUENCE_LENGTH residues)"
echo "       표면: $SURFACE_NAME"
echo "       생성 구조: $NSTRUCT"
echo "       Fragment: 9mer($FRAG_9_COUNT), 3mer($FRAG_3_COUNT)"
echo "       결과 위치: $WORK_DIR"