#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tio2_surface_residue.py
- TiO2 표면 PDB에서 Ti와 P 원자를 분석하여 Rosetta용 params 파일 생성
- 실제 PDB 구조를 분석해서 적절한 잔기명과 좌표계 생성
- 6개 가상원자를 사용한 octahedral 배위 환경 모델링
- 각 원자마다 고유한 잔기번호 할당

Usage:
  python tio2_surface_residue.py --pdb input_surface.pdb \
                                 --out-params params/ \
                                 --out-pdb cleaned_surface.pdb \
                                 [--ti-charge 4] \
                                 [--p-charge 0]
"""
import re
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

def parse_args():
    ap = argparse.ArgumentParser(description="TiO2 표면 구조를 위한 Rosetta params 생성")
    ap.add_argument("--pdb", required=True, help="입력 PDB 파일")
    ap.add_argument("--out-params", default="params", help="params 출력 디렉토리")
    ap.add_argument("--out-pdb", required=True, help="정리된 PDB 출력 파일")
    ap.add_argument("--ti-charge", type=int, default=4, help="Ti 전하 (기본: 4)")
    ap.add_argument("--p-charge", type=int, default=0, help="P 전하 (기본: 0)")
    ap.add_argument("--analyze-only", action="store_true", help="분석만 수행하고 파일 생성 안함")
    return ap.parse_args()

def analyze_pdb_structure(pdb_file):
    """PDB 구조 분석: 원소별 분포, 잔기명 패턴, 좌표 분포"""
    
    ti_atoms = []
    p_atoms = []
    resname_counts = Counter()
    
    with open(pdb_file, 'r') as f:
        for line in f:
            if not line.startswith('HETATM'):
                continue
                
            atom_name = line[12:16].strip()
            resname = line[17:20].strip()
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
            element = line[76:78].strip() if len(line) >= 78 else ""
            
            # Element 추정
            if not element:
                if 'Ti' in atom_name or resname.startswith('Ti'):
                    element = 'Ti'
                elif 'P' in atom_name or resname.startswith('P'):
                    element = 'P'
            
            resname_counts[resname] += 1
            
            if element == 'Ti' or 'Ti' in atom_name:
                ti_atoms.append((atom_name, resname, x, y, z))
            elif element == 'P' or 'P' in atom_name:
                p_atoms.append((atom_name, resname, x, y, z))
    
    return {
        'ti_atoms': ti_atoms,
        'p_atoms': p_atoms,
        'resname_counts': resname_counts,
        'total_ti': len(ti_atoms),
        'total_p': len(p_atoms)
    }

def generate_ti_params(charge=4):
    """Ti 원자용 params 파일 생성 (octahedral 환경)"""
    resname = f"TI{charge}"
    
    return f"""# Ti{charge}+ params based on Rosetta standard format
NAME {resname}
IO_STRING {resname} Z
TYPE LIGAND
PROPERTIES METAL
AA UNK

ATOM TI   CAbb  X    {float(charge):.2f}
ATOM V1   VIRT  VIRT 0.00
ATOM V2   VIRT  VIRT 0.00
ATOM V3   VIRT  VIRT 0.00
ATOM V4   VIRT  VIRT 0.00
ATOM V5   VIRT  VIRT 0.00
ATOM V6   VIRT  VIRT 0.00

BOND TI   V1
BOND TI   V2
BOND TI   V3
BOND TI   V4
BOND TI   V5
BOND TI   V6

CHARGE TI FORMAL +{charge}
NBR_ATOM TI
NBR_RADIUS 0.01

# Octahedral coordination: 6 virtual atoms 
ICOOR_INTERNAL   TI     0.000000    0.000000    0.000000  TI    V1    V2
ICOOR_INTERNAL   V1     0.000000  180.000000    1.000000  TI    V1    V2  # x
ICOOR_INTERNAL   V2     0.000000   90.000000    1.000000  TI    V1    V2  # y
ICOOR_INTERNAL   V3    90.000000   90.000000    1.000000  TI    V2    V1  # z
ICOOR_INTERNAL   V4   180.000000   90.000000    1.000000  TI    V2    V1  # -x
ICOOR_INTERNAL   V5   180.000000   90.000000    1.000000  TI    V1    V2  # -y
ICOOR_INTERNAL   V6   -90.000000   90.000000    1.000000  TI    V2    V1  # -z
"""

def generate_p_params(charge=0):
    """P 원자용 params 파일 생성 (표면 인산기 환경)"""
    resname = "PSF"
    
    charge_str = f"+{charge}" if charge > 0 else f"{charge}" if charge < 0 else "0"
    
    return f"""# Auto-generated P{charge_str} params for TiO2 surface phosphate sites
# Tetrahedral phosphate environment with 4 virtual atoms
NAME {resname}
IO_STRING {resname} X
TYPE LIGAND
AA UNK

ATOM P    Phos  X     {float(charge):.2f}
ATOM V1   VIRT  VIRT  0.00
ATOM V2   VIRT  VIRT  0.00
ATOM V3   VIRT  VIRT  0.00
ATOM V4   VIRT  VIRT  0.00

BOND P    V1
BOND P    V2
BOND P    V3
BOND P    V4

CHARGE P FORMAL {charge_str}
NBR_ATOM P
NBR_RADIUS 0.01

# Tetrahedral coordination: 4 virtual atoms in tetrahedral geometry
ICOOR_INTERNAL   P      0.000000    0.000000    0.000000  P     V1    V2
ICOOR_INTERNAL   V1     0.000000  180.000000    1.800000  P     V1    V2
ICOOR_INTERNAL   V2     0.000000  109.470000    1.800000  P     V1    V2  
ICOOR_INTERNAL   V3   120.000000  109.470000    1.800000  P     V1    V2
ICOOR_INTERNAL   V4  -120.000000  109.470000    1.800000  P     V1    V2
"""

def rewrite_pdb_with_analysis(input_pdb, output_pdb, analysis, ti_charge, p_charge):
    """분석 결과를 바탕으로 PDB 파일 재작성 - 각 원자마다 고유한 잔기번호 할당"""
    
    ti_resname = f"TI{ti_charge}"
    p_resname = "PSF"
    
    changes = {
        'ti_renamed': 0,
        'p_renamed': 0,
        'total_processed': 0
    }
    
    # 잔기 번호 카운터 - 각 원자마다 고유한 번호 할당
    ti_residue_counter = 1
    p_residue_counter = 1001  # P는 1001번부터 시작해서 Ti와 겹치지 않게
    
    with open(input_pdb, 'r') as fin, open(output_pdb, 'w') as fout:
        for line in fin:
            if not line.startswith('HETATM'):
                fout.write(line)
                continue
                
            atom_name = line[12:16].strip()
            resname = line[17:20].strip()
            element = line[76:78].strip() if len(line) >= 78 else ""
            
            # Element 추정
            if not element:
                if 'Ti' in atom_name or resname.startswith('Ti'):
                    element = 'Ti'
                elif 'P' in atom_name or resname.startswith('P'):
                    element = 'P'
            
            new_line = line
            
            # Ti 처리 - 각 Ti마다 고유한 잔기번호
            if element == 'Ti' or 'Ti' in atom_name:
                new_resname = f"{ti_resname:3s}"
                new_atom_name = "TI  "
                new_res_num = f"{ti_residue_counter:4d}"  # 고유한 잔기번호
                
                # PDB 포맷 정확히 지키기
                # 컬럼: 0-6(레코드) 6-11(원자#) 12-16(원자명) 17-20(잔기명) 21(체인) 22-26(잔기#) 26-(나머지)
                new_line = (
                    line[:12] +           # HETATM + 원자번호 (0-12)
                    new_atom_name +       # 원자명 TI (12-16)
                    line[16:17] +         # alt loc (16-17)
                    new_resname +         # 잔기명 TI4 (17-20)
                    line[20:22] +         # 공백 + 체인 (20-22)
                    new_res_num +         # 고유 잔기번호 (22-26)
                    line[26:]             # 나머지 전부 (26-)
                )
                
                ti_residue_counter += 1  # 다음 Ti는 다른 번호
                changes['ti_renamed'] += 1
                
            # P 처리 - 각 P마다 고유한 잔기번호
            elif element == 'P' or 'P' in atom_name:
                new_resname = f"{p_resname:3s}"
                new_atom_name = "P   "
                new_res_num = f"{p_residue_counter:4d}"  # 고유한 잔기번호
                
                new_line = (
                    line[:12] +           # HETATM + 원자번호
                    new_atom_name +       # 원자명 P
                    line[16:17] +         # alt loc
                    new_resname +         # 잔기명 PSF
                    line[20:22] +         # 공백 + 체인
                    new_res_num +         # 고유 잔기번호
                    line[26:]             # 나머지
                )
                
                p_residue_counter += 1  # 다음 P는 다른 번호
                changes['p_renamed'] += 1
            
            fout.write(new_line)
            changes['total_processed'] += 1
    
    print(f"\n=== Residue Numbering ===")
    print(f"Ti residues numbered: 1 to {ti_residue_counter-1}")
    print(f"P residues numbered: 1001 to {p_residue_counter-1}")
    
    return changes

def print_analysis_summary(analysis, ti_charge, p_charge):
    """분석 결과 요약 출력"""
    print("=== TiO2 Surface Structure Analysis ===")
    print(f"Total Ti atoms: {analysis['total_ti']}")
    print(f"Total P atoms: {analysis['total_p']}")
    print()
    
    print("Original residue name distribution:")
    for resname, count in analysis['resname_counts'].most_common():
        print(f"  {resname}: {count} atoms")
    print()
    
    if analysis['ti_atoms']:
        ti_coords = np.array([(x, y, z) for _, _, x, y, z in analysis['ti_atoms']])
        print(f"Ti coordinate ranges:")
        print(f"  X: {ti_coords[:, 0].min():.3f} to {ti_coords[:, 0].max():.3f}")
        print(f"  Y: {ti_coords[:, 1].min():.3f} to {ti_coords[:, 1].max():.3f}")
        print(f"  Z: {ti_coords[:, 2].min():.3f} to {ti_coords[:, 2].max():.3f}")
        print()
    
    if analysis['p_atoms']:
        p_coords = np.array([(x, y, z) for _, _, x, y, z in analysis['p_atoms']])
        print(f"P coordinate ranges:")
        print(f"  X: {p_coords[:, 0].min():.3f} to {p_coords[:, 0].max():.3f}")
        print(f"  Y: {p_coords[:, 1].min():.3f} to {p_coords[:, 1].max():.3f}")
        print(f"  Z: {p_coords[:, 2].min():.3f} to {p_coords[:, 2].max():.3f}")
        print()
    
    print("Proposed residue names:")
    print(f"  Ti → TI{ti_charge} (Ti{ti_charge}+ with octahedral coordination)")
    print(f"  P → PSF (Surface phosphate unit)")
    print()

def main():
    args = parse_args()
    
    # PDB 구조 분석
    print("Analyzing PDB structure...")
    analysis = analyze_pdb_structure(args.pdb)
    
    # 분석 결과 출력
    print_analysis_summary(analysis, args.ti_charge, args.p_charge)
    
    if args.analyze_only:
        return 0
    
    # Params 디렉토리 생성
    os.makedirs(args.out_params, exist_ok=True)
    
    # Params 파일 생성
    params_written = []
    
    if analysis['total_ti'] > 0:
        ti_resname = f"TI{args.ti_charge}"
        ti_params_path = Path(args.out_params) / f"{ti_resname}.params"
        ti_params_path.write_text(generate_ti_params(args.ti_charge))
        params_written.append(ti_params_path.name)
        print(f"Generated: {ti_params_path}")
    
    if analysis['total_p'] > 0:
        p_params_path = Path(args.out_params) / "PSF.params"
        p_params_path.write_text(generate_p_params(args.p_charge))
        params_written.append(p_params_path.name)
        print(f"Generated: {p_params_path}")
    
    # PDB 파일 재작성 (각 원자마다 고유한 잔기번호)
    print(f"\nRewriting PDB file: {args.out_pdb}")
    changes = rewrite_pdb_with_analysis(
        args.pdb, args.out_pdb, analysis, args.ti_charge, args.p_charge
    )
    
    # 최종 요약
    print("\n=== Summary ===")
    print(f"Ti atoms renamed to TI{args.ti_charge}: {changes['ti_renamed']}")
    print(f"P atoms renamed to PSF: {changes['p_renamed']}")
    print(f"Total atoms processed: {changes['total_processed']}")
    print(f"Params files created: {', '.join(params_written)}")
    print(f"Cleaned PDB: {args.out_pdb}")
    
    print("\n=== Rosetta Usage ===")
    print("Load these params files in Rosetta:")
    for param_file in params_written:
        print(f"  -extra_res_fa params/{param_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())