#!/usr/bin/env python3
"""
PDB 파일 병합기 (RosettaSurface용)
usage: python merge_pdb_files.py --protein albumin --surface TiO2 --output merged.pdb
"""
import os
import argparse
import numpy as np
from pathlib import Path

# 금속별 잔기 매핑
METAL_MAPPING = {
    'Ti': 'TI4', 'Ca': 'CA2', 'Zn': 'ZN2', 'Mg': 'MG2', 
    'Cu': 'CU2', 'Fe': 'FE2', 'Al': 'AL3', 'Ni': 'NI2'
}

ANION_MAPPING = {
    'O': 'O2M', 'OH': 'OH1M', 'CO3': 'CO3', 'PO4': 'PO4'
}

def read_pdb_file(filepath):
    """PDB 파일 읽기"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")
    
    with open(filepath, 'r') as f:
        lines = [line.rstrip() for line in f.readlines()]
    
    return lines

def identify_atom_type(atom_name, line):
    """원자 타입 식별 (금속/음이온 매핑)"""
    atom_clean = atom_name.strip().upper()
    
    # 금속 이온 확인
    for metal, residue in METAL_MAPPING.items():
        if metal.upper() in atom_clean:
            return residue, metal
    
    # 음이온 확인
    for anion, residue in ANION_MAPPING.items():
        if anion.upper() in atom_clean:
            return residue, anion
    
    # 기본값 (원소 기준)
    if atom_clean.startswith('TI'):
        return 'TI4', 'Ti'
    elif atom_clean.startswith('CA'):
        return 'CA2', 'Ca'  
    elif atom_clean.startswith('O'):
        return 'O2M', 'O'
    else:
        return 'UNK', atom_clean[:2]

def process_surface_atoms(lines, surface_chain='S'):
    """표면 원자들을 HETATM으로 변환"""
    processed = []
    atom_count = 1
    res_count = 1
    current_res = None
    
    for line in lines:
        if line.startswith(('ATOM', 'HETATM')):
            try:
                # PDB 라인 파싱
                atom_name = line[12:16].strip()
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                occupancy = float(line[54:60]) if len(line) > 54 and line[54:60].strip() else 1.00
                b_factor = float(line[60:66]) if len(line) > 60 and line[60:66].strip() else 0.00
                
                # 원자 타입 식별
                residue_name, element = identify_atom_type(atom_name, line)
                
                # Residue 번호 관리
                if residue_name != current_res:
                    current_res = residue_name
                    res_count += 1
                
                # HETATM 형식으로 변환
                hetatm_line = (
                    f"HETATM{atom_count:5d}  {element:<2}  {residue_name} {surface_chain}{res_count:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}{occupancy:6.2f}{b_factor:6.2f}          {element:>2}"
                )
                
                processed.append(hetatm_line)
                atom_count += 1
                
            except (ValueError, IndexError) as e:
                print(f"[WARNING] 잘못된 표면 PDB 라인 건너뛰기: {line[:20]}...")
                continue
    
    return processed

def process_protein_atoms(lines, protein_chain='P', start_atom_num=1):
    """단백질 원자들을 ATOM으로 처리"""
    processed = []
    atom_count = start_atom_num
    
    for line in lines:
        if line.startswith('ATOM'):
            try:
                # 체인 ID와 원자 번호 업데이트
                new_line = f"ATOM  {atom_count:5d}{line[11:21]}{protein_chain}{line[22:]}"
                processed.append(new_line)
                atom_count += 1
            except (ValueError, IndexError):
                processed.append(line)  # 원본 유지
                
        elif line.startswith(('HETATM', 'TER', 'END', 'CONECT')):
            processed.append(line)
    
    return processed, atom_count

def calculate_bounding_box(lines):
    """원자 좌표들의 bounding box 계산"""
    coords = []
    
    for line in lines:
        if line.startswith(('ATOM', 'HETATM')):
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                coords.append([x, y, z])
            except (ValueError, IndexError):
                continue
    
    if not coords:
        return None
    
    coords = np.array(coords)
    min_coords = np.min(coords, axis=0)
    max_coords = np.max(coords, axis=0)
    center = (min_coords + max_coords) / 2
    
    return {
        'min': min_coords,
        'max': max_coords,
        'center': center,
        'size': max_coords - min_coords
    }

def translate_atoms(lines, translation_vector):
    """원자 좌표를 지정된 벡터만큼 이동"""
    translated = []
    dx, dy, dz = translation_vector
    
    for line in lines:
        if line.startswith(('ATOM', 'HETATM')):
            try:
                x = float(line[30:38]) + dx
                y = float(line[38:46]) + dy
                z = float(line[46:54]) + dz
                
                new_line = f"{line[:30]}{x:8.3f}{y:8.3f}{z:8.3f}{line[54:]}"
                translated.append(new_line)
            except (ValueError, IndexError):
                translated.append(line)
        else:
            translated.append(line)
    
    return translated

def position_protein_above_surface(protein_lines, surface_lines, gap=10.0):
    """단백질을 표면 위에 배치"""
    
    # 표면과 단백질의 bounding box 계산
    surface_bbox = calculate_bounding_box(surface_lines)
    protein_bbox = calculate_bounding_box(protein_lines)
    
    if not surface_bbox or not protein_bbox:
        print("[WARNING] Bounding box 계산 실패, 원본 좌표 사용")
        return protein_lines
    
    # 단백질을 표면 중심 위에 배치
    target_x = surface_bbox['center'][0] - protein_bbox['center'][0]
    target_y = surface_bbox['center'][1] - protein_bbox['center'][1]
    target_z = surface_bbox['max'][2] + gap - protein_bbox['min'][2]
    
    translation = [target_x, target_y, target_z]
    
    print(f"[INFO] 단백질 위치 조정:")
    print(f"       표면 중심: ({surface_bbox['center'][0]:.1f}, {surface_bbox['center'][1]:.1f}, {surface_bbox['center'][2]:.1f})")
    print(f"       표면 최고점: {surface_bbox['max'][2]:.1f}")
    print(f"       단백질 이동: ({translation[0]:.1f}, {translation[1]:.1f}, {translation[2]:.1f})")
    
    return translate_atoms(protein_lines, translation)

def merge_pdb_files(protein_path, surface_path, output_path, 
                   protein_chain='P', surface_chain='S', gap=10.0):
    """PDB 파일들을 RosettaSurface 형식으로 병합"""
    
    print(f"[INFO] PDB 파일 병합 시작")
    print(f"       단백질: {protein_path} (체인 {protein_chain})")
    print(f"       표면: {surface_path} (체인 {surface_chain})")
    print(f"       출력: {output_path}")
    
    # 파일 읽기
    protein_lines = read_pdb_file(protein_path)
    surface_lines = read_pdb_file(surface_path)
    
    # 표면 처리 (HETATM으로)
    print(f"[INFO] 표면 원자 처리 중...")
    processed_surface = process_surface_atoms(surface_lines, surface_chain)
    
    # 단백질 처리 (ATOM으로)
    print(f"[INFO] 단백질 원자 처리 중...")
    processed_protein, _ = process_protein_atoms(
        protein_lines, protein_chain, len(processed_surface) + 1
    )
    
    # 단백질 위치 조정
    positioned_protein = position_protein_above_surface(
        processed_protein, processed_surface, gap
    )
    
    # 출력 디렉토리 생성
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 병합된 PDB 작성
    with open(output_path, 'w') as f:
        # 헤더
        f.write("REMARK   1 MERGED PDB FOR ROSETTASURFACE\n")
        f.write(f"REMARK   2 SURFACE: {Path(surface_path).name} (CHAIN {surface_chain})\n")
        f.write(f"REMARK   3 PROTEIN: {Path(protein_path).name} (CHAIN {protein_chain})\n")
        f.write("REMARK   4 FORMAT: SURFACE=HETATM, PROTEIN=ATOM\n")
        
        # 표면 좌표 (HETATM)
        for line in processed_surface:
            f.write(line + "\n")
        
        # 체인 구분
        f.write("TER\n")
        
        # 단백질 좌표 (ATOM)
        for line in positioned_protein:
            if not line.startswith(('TER', 'END')):
                f.write(line + "\n")
        
        # 파일 종료
        f.write("END\n")
    
    # 통계 출력
    surface_atoms = len(processed_surface)
    protein_atoms = len([l for l in positioned_protein if l.startswith('ATOM')])
    
    print(f"[SUCCESS] 병합 완료!")
    print(f"          표면 원자: {surface_atoms}개 (HETATM)")
    print(f"          단백질 원자: {protein_atoms}개 (ATOM)")
    print(f"          출력 파일: {output_path}")
    
    return output_path

def find_input_files(protein_name, surface_name, input_base="input"):
    """입력 파일들 자동 검색"""
    input_path = Path(input_base)
    
    # 단백질 파일 검색
    protein_candidates = [
        input_path / "protein" / protein_name / f"{protein_name}.pdb",
        input_path / "proteins" / f"{protein_name}.pdb",
        input_path / f"{protein_name}.pdb"
    ]
    
    protein_file = None
    for candidate in protein_candidates:
        if candidate.exists():
            protein_file = str(candidate)
            break
    
    # 표면 파일 검색
    surface_candidates = [
        input_path / "metal" / surface_name / f"{surface_name}.pdb",
        input_path / "surface" / f"{surface_name}.pdb",
        input_path / "surfaces" / f"{surface_name}.pdb",
        input_path / f"{surface_name}.pdb"
    ]
    
    surface_file = None
    for candidate in surface_candidates:
        if candidate.exists():
            surface_file = str(candidate)
            break
    
    return protein_file, surface_file

def parse_args():
    parser = argparse.ArgumentParser(description='PDB 파일 병합기 (RosettaSurface용)')
    
    # 파일 지정 방식 1: 직접 경로 (우선)
    parser.add_argument('--protein-file', 
                       help='단백질 PDB 파일 경로')
    parser.add_argument('--surface-file',
                       help='표면 PDB 파일 경로')
    
    # 파일 지정 방식 2: 이름으로 자동 검색 (호환성)
    parser.add_argument('--protein', 
                       help='단백질 이름 (자동 경로 검색)')
    parser.add_argument('--surface',
                       help='표면 이름 (자동 경로 검색)')
    parser.add_argument('--input-base', default='input',
                       help='입력 기본 디렉토리 (기본: input)')
    
    # 출력 설정
    parser.add_argument('--output', required=True,
                       help='출력 PDB 파일 경로')
    parser.add_argument('--protein-chain', default='P',
                       help='단백질 체인 ID (기본: P)')
    parser.add_argument('--surface-chain', default='S', 
                       help='표면 체인 ID (기본: S)')
    parser.add_argument('--gap', type=float, default=10.0,
                       help='단백질-표면 간격 (Angstrom, 기본: 10.0)')
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    try:
        # 입력 파일 결정 (직접 경로 우선)
        if args.protein_file and args.surface_file:
            # 직접 경로 지정 (우선순위)
            protein_path = args.protein_file
            surface_path = args.surface_file
        elif args.protein and args.surface:
            # 이름으로 자동 검색 (호환성)
            protein_path, surface_path = find_input_files(
                args.protein, args.surface, args.input_base
            )
            if not protein_path:
                print(f"[ERROR] 단백질 파일을 찾을 수 없습니다: {args.protein}")
                print(f"        검색 경로: {args.input_base}/protein/{args.protein}/{args.protein}.pdb")
                return 1
            if not surface_path:
                print(f"[ERROR] 표면 파일을 찾을 수 없습니다: {args.surface}")
                print(f"        검색 경로: {args.input_base}/metal/{args.surface}/{args.surface}.pdb")
                return 1
        else:
            print("[ERROR] 파일 지정 방법:")
            print("        1. --protein-file, --surface-file로 직접 경로 지정")
            print("        2. --protein, --surface로 이름 지정 (자동 검색)")
            return 1
        
        # PDB 병합 실행
        output_path = merge_pdb_files(
            protein_path, surface_path, args.output,
            args.protein_chain, args.surface_chain, args.gap
        )
        
        print(f"\n[INFO] 다음 단계:")
        print(f"       1. Fragment 파일 생성 (Robetta 서버)")
        print(f"       2. 표면 벡터 파일 준비")
        print(f"       3. 금속 params 파일 준비")
        print(f"       4. RosettaSurface 실행")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())