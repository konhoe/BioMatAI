#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
protein_surface_merger.py
- 단백질 PDB와 TiO2 표면 PDB를 Rosetta 양식에 맞게 병합
- Chain ID, 원자 번호, 잔기 번호 자동 조정
- 표면 HETATM은 각각 개별 잔기로 처리
- TER 레코드 적절히 삽입
- HETATM vs ATOM 분류 유지

Usage:
  python protein_surface_merger.py --protein protein.pdb \
                                   --surface cleaned_surface.pdb \
                                   --output merged_system.pdb \
                                   [--protein-chain A] \
                                   [--surface-chain S] \
                                   [--gap 10.0]
"""

import argparse
import sys
from pathlib import Path

def parse_args():
    ap = argparse.ArgumentParser(description="단백질과 TiO2 표면을 Rosetta 양식으로 병합")
    ap.add_argument("--protein", required=True, help="단백질 PDB 파일")
    ap.add_argument("--surface", required=True, help="정리된 표면 PDB 파일")
    ap.add_argument("--output", required=True, help="병합된 PDB 출력 파일")
    ap.add_argument("--protein-chain", default="A", help="단백질 chain ID (기본: A)")
    ap.add_argument("--surface-chain", default="S", help="표면 chain ID (기본: S)")
    ap.add_argument("--gap", type=float, default=10.0, help="단백질-표면 간 최소 거리 (Å)")
    ap.add_argument("--z-offset", type=float, help="표면 Z 좌표 오프셋 (수동 조정)")
    return ap.parse_args()

def read_pdb_records(pdb_file):
    """PDB 파일을 읽어서 ATOM/HETATM 레코드들을 분류해서 반환"""
    atom_records = []
    hetatm_records = []
    header_records = []
    
    with open(pdb_file, 'r') as f:
        for line in f:
            line = line.rstrip('\n\r')
            record_type = line[:6].strip()
            
            if record_type == "ATOM":
                atom_records.append(line)
            elif record_type == "HETATM":
                hetatm_records.append(line)
            elif record_type in ["HEADER", "TITLE", "COMPND", "SOURCE", "REMARK"]:
                header_records.append(line)
            # TER, END 등은 나중에 다시 생성
    
    return {
        'atom_records': atom_records,
        'hetatm_records': hetatm_records,
        'header_records': header_records
    }

def get_coordinate_bounds(records):
    """ATOM/HETATM 레코드들로부터 좌표 범위 계산"""
    if not records:
        return None
    
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')
    
    for line in records:
        if len(line) >= 54:
            try:
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
                
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                min_z, max_z = min(min_z, z), max(max_z, z)
            except ValueError:
                continue
    
    return {
        'min': (min_x, min_y, min_z),
        'max': (max_x, max_y, max_z),
        'center': ((min_x + max_x)/2, (min_y + max_y)/2, (min_z + max_z)/2)
    }

def renumber_and_rechain(records, start_atom_num=1, start_res_num=1, chain_id="A"):
    """원자 번호, 잔기 번호, chain ID 재할당"""
    if not records:
        return [], start_atom_num, start_res_num
    
    renumbered = []
    current_atom_num = start_atom_num
    current_res_num = start_res_num
    last_original_res_num = None
    
    for line in records:
        if len(line) < 26:
            renumbered.append(line)
            continue
            
        try:
            original_res_num = int(line[22:26].strip())
        except ValueError:
            original_res_num = current_res_num
        
        # 새로운 잔기가 시작되면 잔기 번호 증가
        if last_original_res_num is not None and original_res_num != last_original_res_num:
            current_res_num += 1
        last_original_res_num = original_res_num
        
        # 새로운 라인 구성
        new_line = (
            line[:6] +                                    # Record type
            f"{current_atom_num:5d}" +                   # Atom number
            line[11:21] +                                # Atom name, alt loc, res name
            chain_id +                                   # Chain ID
            f"{current_res_num:4d}" +                    # Residue number
            line[26:]                                    # Rest of line
        )
        
        renumbered.append(new_line)
        current_atom_num += 1
    
    return renumbered, current_atom_num, current_res_num + 1

def renumber_and_rechain_hetatm(records, start_atom_num=1, chain_id="S"):
    """HETATM 레코드들을 각각 고유한 잔기번호로 재할당 (개별 원자 = 개별 잔기)"""
    if not records:
        return [], start_atom_num
    
    renumbered = []
    current_atom_num = start_atom_num
    current_res_num = 1  # 잔기 번호는 1부터 시작
    
    for line in records:
        if len(line) < 26:
            renumbered.append(line)
            continue
        
        # 각 HETATM 원자마다 고유한 잔기 번호 할당
        new_line = (
            line[:6] +                                    # Record type (HETATM)
            f"{current_atom_num:5d}" +                   # Atom number
            line[11:21] +                                # Atom name, alt loc, res name
            chain_id +                                   # Chain ID
            f"{current_res_num:4d}" +                    # 고유한 잔기 번호
            line[26:]                                    # Rest of line
        )
        
        renumbered.append(new_line)
        current_atom_num += 1
        current_res_num += 1  # 다음 원자는 다른 잔기 번호
    
    return renumbered, current_atom_num

def translate_coordinates(records, offset_x=0.0, offset_y=0.0, offset_z=0.0):
    """좌표 이동"""
    if not records:
        return records
    
    translated = []
    for line in records:
        if len(line) >= 54 and line[:6].strip() in ["ATOM", "HETATM"]:
            try:
                x = float(line[30:38].strip()) + offset_x
                y = float(line[38:46].strip()) + offset_y
                z = float(line[46:54].strip()) + offset_z
                
                new_line = (
                    line[:30] +
                    f"{x:8.3f}" +
                    f"{y:8.3f}" +
                    f"{z:8.3f}" +
                    line[54:]
                )
                translated.append(new_line)
            except ValueError:
                translated.append(line)
        else:
            translated.append(line)
    
    return translated

def calculate_surface_offset(protein_bounds, surface_bounds, gap):
    """표면을 단백질 아래쪽에 적절한 거리로 배치하기 위한 offset 계산"""
    if not protein_bounds or not surface_bounds:
        return 0.0, 0.0, 0.0
    
    # 단백질 중심에 표면 중심을 맞춤 (X, Y)
    offset_x = protein_bounds['center'][0] - surface_bounds['center'][0]
    offset_y = protein_bounds['center'][1] - surface_bounds['center'][1]
    
    # 표면을 단백질 아래쪽에 gap만큼 떨어뜨림 (Z)
    protein_min_z = protein_bounds['min'][2]
    surface_max_z = surface_bounds['max'][2]
    offset_z = protein_min_z - surface_max_z - gap
    
    return offset_x, offset_y, offset_z

def merge_pdb_files(protein_file, surface_file, output_file, 
                   protein_chain="A", surface_chain="S", gap=10.0, z_offset=None):
    """PDB 파일들을 병합 - 표면 원자들을 각각 개별 잔기로 처리"""
    
    print(f"Reading protein file: {protein_file}")
    protein_data = read_pdb_records(protein_file)
    
    print(f"Reading surface file: {surface_file}")
    surface_data = read_pdb_records(surface_file)
    
    # 좌표 범위 분석
    protein_bounds = get_coordinate_bounds(protein_data['atom_records'])
    surface_bounds = get_coordinate_bounds(
        surface_data['atom_records'] + surface_data['hetatm_records']
    )
    
    print("\n=== Coordinate Analysis ===")
    if protein_bounds:
        print(f"Protein bounds:")
        print(f"  X: {protein_bounds['min'][0]:.1f} to {protein_bounds['max'][0]:.1f}")
        print(f"  Y: {protein_bounds['min'][1]:.1f} to {protein_bounds['max'][1]:.1f}")
        print(f"  Z: {protein_bounds['min'][2]:.1f} to {protein_bounds['max'][2]:.1f}")
        print(f"  Center: ({protein_bounds['center'][0]:.1f}, {protein_bounds['center'][1]:.1f}, {protein_bounds['center'][2]:.1f})")
    
    if surface_bounds:
        print(f"Surface bounds:")
        print(f"  X: {surface_bounds['min'][0]:.1f} to {surface_bounds['max'][0]:.1f}")
        print(f"  Y: {surface_bounds['min'][1]:.1f} to {surface_bounds['max'][1]:.1f}")
        print(f"  Z: {surface_bounds['min'][2]:.1f} to {surface_bounds['max'][2]:.1f}")
        print(f"  Center: ({surface_bounds['center'][0]:.1f}, {surface_bounds['center'][1]:.1f}, {surface_bounds['center'][2]:.1f})")
    
    # 표면 오프셋 계산
    if z_offset is not None:
        offset_x, offset_y, offset_z = 0.0, 0.0, z_offset
        print(f"\nUsing manual Z offset: {z_offset:.1f}")
    else:
        offset_x, offset_y, offset_z = calculate_surface_offset(protein_bounds, surface_bounds, gap)
        print(f"\nCalculated surface offset: ({offset_x:.1f}, {offset_y:.1f}, {offset_z:.1f})")
    
    # 단백질 처리 (chain A, 원자 번호 1부터)
    protein_atoms, next_atom_num, next_res_num = renumber_and_rechain(
        protein_data['atom_records'], 
        start_atom_num=1, 
        start_res_num=1, 
        chain_id=protein_chain
    )
    
    # 표면 좌표 이동
    surface_atoms_moved = translate_coordinates(
        surface_data['atom_records'], offset_x, offset_y, offset_z
    )
    surface_hetatm_moved = translate_coordinates(
        surface_data['hetatm_records'], offset_x, offset_y, offset_z
    )
    
    # 표면 원자들 재번호 (ATOM이 있다면)
    surface_atoms, next_atom_num, next_res_num = renumber_and_rechain(
        surface_atoms_moved,
        start_atom_num=next_atom_num,
        start_res_num=next_res_num,
        chain_id=surface_chain
    )
    
    # ⭐ 핵심: 표면 HETATM들을 각각 개별 잔기로 처리
    surface_hetatm, final_atom_num = renumber_and_rechain_hetatm(
        surface_hetatm_moved,
        start_atom_num=next_atom_num,
        chain_id=surface_chain
    )
    
    # 병합된 파일 작성
    print(f"\nWriting merged file: {output_file}")
    with open(output_file, 'w') as f:
        # 단백질 ATOM 레코드
        if protein_atoms:
            for line in protein_atoms:
                f.write(line + '\n')
        
        # 표면 ATOM 레코드 (있다면)
        if surface_atoms:
            for line in surface_atoms:
                f.write(line + '\n')
        
        # 표면 HETATM 레코드 (각각 개별 잔기)
        if surface_hetatm:
            for line in surface_hetatm:
                f.write(line + '\n')
        
        f.write("END\n")
    
    # 통계 출력
    print(f"\n=== Merge Summary ===")
    print(f"Protein ATOM records: {len(protein_atoms)}")
    print(f"Surface ATOM records: {len(surface_atoms)}")
    print(f"Surface HETATM records: {len(surface_hetatm)} (각각 개별 잔기)")
    print(f"Total records: {len(protein_atoms) + len(surface_atoms) + len(surface_hetatm)}")
    print(f"Surface HETATM residue numbers: 1 to {len(surface_hetatm)}")
    print(f"Output file: {output_file}")

def main():
    args = parse_args()
    
    # 파일 존재 확인
    if not Path(args.protein).exists():
        print(f"Error: Protein file not found: {args.protein}")
        return 1
    
    if not Path(args.surface).exists():
        print(f"Error: Surface file not found: {args.surface}")
        return 1
    
    # 병합 실행
    merge_pdb_files(
        protein_file=args.protein,
        surface_file=args.surface,
        output_file=args.output,
        protein_chain=args.protein_chain,
        surface_chain=args.surface_chain,
        gap=args.gap,
        z_offset=args.z_offset
    )
    
    return 0

if __name__ == "__main__":
    sys.exit(main())