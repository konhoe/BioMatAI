#!/usr/bin/env bash
set -euo pipefail

# 범용 SurfRosetta 도킹 스크립트
# 사용법: ./generate_surfrosetta.sh <protein_name> <surface_name> [nstruct]

# 인자 확인
if [[ $# -lt 2 ]]; then
    echo "사용법: $0 <protein_name> <surface_name> [nstruct]"
    echo "예시: $0 small_albumin TiP2 3"
    echo "예시: $0 insulin Au 5"
    exit 1
fi

PROTEIN_NAME="$1"
SURFACE_NAME="$2"
NSTRUCT="${3:-3}"  # 기본값 3

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

echo "[INFO] SurfRosetta 도킹 시작"
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

# 실험 디렉토리 생성
mkdir -p "$WORK_DIR"/{input,output,logs,analysis}
cd "$WORK_DIR"

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

# Fragment 파일 생성
echo "[INFO] Fragment 파일 생성 중..."

# 병합된 PDB에서 실제 단백질 잔기 범위 확인
FIRST_RES=$(grep "^ATOM" "$MERGED_PDB" | grep " A " | awk '{print $6}' | sort -n | head -1 2>/dev/null || echo 1)
LAST_RES=$(grep "^ATOM" "$MERGED_PDB" | grep " A " | awk '{print $6}' | sort -n | tail -1 2>/dev/null || echo 0)
ACTUAL_RESIDUE_COUNT=$((LAST_RES - FIRST_RES + 1))

echo "[DEBUG] 병합된 PDB의 잔기 범위: $FIRST_RES-$LAST_RES (총 $ACTUAL_RESIDUE_COUNT 개)"

# Fragment 생성 길이 = 실제 잔기 수
FRAGMENT_LENGTH=$ACTUAL_RESIDUE_COUNT

# 9mer fragment 생성 - 실제 PDB 잔기 수 기준
> input/${PROTEIN_NAME}_9mers

if [[ $FRAGMENT_LENGTH -lt 9 ]]; then
    echo "[ERROR] 구조가 너무 짧습니다 ($FRAGMENT_LENGTH < 9). 9mer fragment를 생성할 수 없습니다."
    exit 1
fi

MAX_9MER_POS=$((FRAGMENT_LENGTH - 8))
echo "[DEBUG] 9mer positions: 1 to $MAX_9MER_POS (PDB 잔기 수: $FRAGMENT_LENGTH)"

for pos in $(seq 1 $MAX_9MER_POS); do
    echo " position:            $pos neighbors:          200" >> input/${PROTEIN_NAME}_9mers
    echo "" >> input/${PROTEIN_NAME}_9mers
    
    # 각 position에서 9개 아미노산 처리
    for i in $(seq 0 8); do
        seq_pos=$((pos + i))
        if [[ $seq_pos -le $SEQUENCE_LENGTH ]]; then
            seq_idx=$((seq_pos - 1))  # 0-based index for SEQUENCE
            aa="${SEQUENCE:$seq_idx:1}"
        else
            aa="A"  # 기본값 (시퀀스 길이 초과시)
        fi
        res_num=$((182 + i))
        echo " 2csb A   $res_num $aa L  -74.810  164.036  180.795   -0.505    6.791    25.816 3     0.000 P  1 F  1" >> input/${PROTEIN_NAME}_9mers
    done
    echo "" >> input/${PROTEIN_NAME}_9mers
done

# 3mer fragment 생성 - 실제 PDB 잔기 수 기준
> input/${PROTEIN_NAME}_3mers

if [[ $FRAGMENT_LENGTH -lt 3 ]]; then
    echo "[ERROR] 구조가 너무 짧습니다 ($FRAGMENT_LENGTH < 3). 3mer fragment를 생성할 수 없습니다."
    exit 1
fi

MAX_3MER_POS=$((FRAGMENT_LENGTH - 2))
echo "[DEBUG] 3mer positions: 1 to $MAX_3MER_POS (PDB 잔기 수: $FRAGMENT_LENGTH)"

for pos in $(seq 1 $MAX_3MER_POS); do
    echo " position:            $pos neighbors:          200" >> input/${PROTEIN_NAME}_3mers
    echo "" >> input/${PROTEIN_NAME}_3mers
    
    # 각 position에서 3개 아미노산 처리
    for i in $(seq 0 2); do
        seq_pos=$((pos + i))
        if [[ $seq_pos -le $SEQUENCE_LENGTH ]]; then
            seq_idx=$((seq_pos - 1))  # 0-based index for SEQUENCE
            aa="${SEQUENCE:$seq_idx:1}"
        else
            aa="A"  # 기본값 (시퀀스 길이 초과시)
        fi
        res_num=$((210 + i))
        echo " 2q52 A   $res_num $aa L  -64.109  141.950 -176.586   -0.911    4.490    17.477 3     0.000 P  1 F  1" >> input/${PROTEIN_NAME}_3mers
    done
    echo "" >> input/${PROTEIN_NAME}_3mers
done

echo "[OK] Fragment 파일 생성 완료"
echo "     9mer: $(wc -l input/${PROTEIN_NAME}_9mers | awk '{print $1}') lines"
echo "     3mer: $(wc -l input/${PROTEIN_NAME}_3mers | awk '{print $1}') lines"

# flags 파일 생성 (예시와 완전히 맞춤 + 에러 방지)
cat > input/flags_${EXP_NAME} << EOF
-s $(basename "$MERGED_PDB")
-include_surfaces
-mute all
-unmute protocols.SurfaceDocking
-overwrite
-nstruct $NSTRUCT
-out:path:pdb output
-out:path:score output
-in:file:frag9 ${PROTEIN_NAME}_9mers
-in:file:frag3 ${PROTEIN_NAME}_3mers
-in:file:surface_vectors ${SURFACE_NAME}.surf
-run:test_cycles True
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

# SurfRosetta 실행
cd input
"$BIN" @flags_${EXP_NAME} 2>&1 | tee ../logs/surfrosetta.log

cd ..

# 결과 확인
echo ""
echo "[INFO] SurfRosetta 실행 완료"
echo "       완료 시간: $(date)"
echo "       작업 디렉토리: $WORK_DIR"
echo "       로그 파일: logs/surfrosetta.log"

if [[ -f "output/score.sc" ]]; then
    RESULT_COUNT=$(ls output/*.pdb 2>/dev/null | wc -l)
    echo "[SUCCESS] 결과 생성 완료!"
    echo "          점수 파일: output/score.sc"
    echo "          PDB 파일: ${RESULT_COUNT}개"
    
    if [[ -s "output/score.sc" ]]; then
        echo ""
        echo "[INFO] 상위 점수들:"
        head -10 "output/score.sc"
    fi
else
    echo "[ERROR] 결과가 생성되지 않았습니다. 로그를 확인하세요:"
    echo "        tail -20 logs/surfrosetta.log"
fi

echo ""
echo "[INFO] 실험 요약:"
echo "       단백질: $PROTEIN_NAME ($SEQUENCE_LENGTH residues)"
echo "       표면: $SURFACE_NAME"
echo "       생성 구조: $NSTRUCT"
echo "       결과 위치: $WORK_DIR"