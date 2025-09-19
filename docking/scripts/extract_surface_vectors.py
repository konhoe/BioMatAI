#!/usr/bin/env python3
"""
표면 벡터 추출 스크립트
PDB 파일에서 표면의 주기적 벡터 3개를 추출
"""

import numpy as np
import os
from collections import defaultdict

def read_pdb_coordinates(pdb_file):
    """PDB 파일에서 원자 좌표 읽기"""
    atoms = []
    with open(pdb_file, 'r') as f:
        for line in f:
            if line.startswith('HETATM') or line.startswith('ATOM'):
                x = float(line[30:38].strip())
                y = float(line[38:46].strip()) 
                z = float(line[46:54].strip())
                element = line[76:78].strip()
                atoms.append([x, y, z, element])
    return np.array(atoms)

def find_surface_plane(atoms):
    """원자들로부터 표면 평면 찾기 (PCA 사용)"""
    coords = atoms[:, :3].astype(float)
    
    # 중심점으로 이동
    center = np.mean(coords, axis=0)
    centered = coords - center
    
    # PCA 수행
    cov_matrix = np.cov(centered.T)
    eigenvals, eigenvecs = np.linalg.eigh(cov_matrix)
    
    # 가장 작은 고유값에 해당하는 벡터가 표면 법선
    normal_vector = eigenvecs[:, 0]
    
    return center, normal_vector, eigenvecs

def extract_lattice_vectors(atoms, center, normal_vector):
    """격자 벡터 추출"""
    coords = atoms[:, :3].astype(float)
    
    # 표면에 투영
    projected = []
    for coord in coords:
        # 표면 평면에 투영
        v = coord - center
        proj = v - np.dot(v, normal_vector) * normal_vector
        projected.append(proj + center)
    
    projected = np.array(projected)
    
    # 가장 가까운 이웃들 찾기
    distances = []
    vectors = []
    
    for i, atom1 in enumerate(projected):
        for j, atom2 in enumerate(projected):
            if i != j:
                vec = atom2 - atom1
                dist = np.linalg.norm(vec)
                if 1.0 < dist < 10.0:  # 적절한 거리 범위
                    distances.append(dist)
                    vectors.append(vec)
    
    # 거리별로 그룹화
    dist_groups = defaultdict(list)
    for dist, vec in zip(distances, vectors):
        dist_groups[round(dist, 1)].append(vec)
    
    # 가장 빈번한 거리들의 벡터 선택
    frequent_distances = sorted(dist_groups.keys(), key=lambda x: len(dist_groups[x]), reverse=True)
    
    lattice_vectors = []
    for dist in frequent_distances[:3]:
        # 각 거리 그룹에서 대표 벡터 선택
        group_vectors = dist_groups[dist]
        mean_vector = np.mean(group_vectors, axis=0)
        lattice_vectors.append(mean_vector)
        if len(lattice_vectors) >= 3:
            break
    
    return lattice_vectors

def create_surface_file(vectors, output_file):
    """표면 벡터 파일 생성"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        for vec in vectors:
            f.write(f"{vec[0]:8.3f} {vec[1]:8.3f} {vec[2]:8.3f}\n")
    
    print(f"표면 벡터 파일 생성: {output_file}")
    print("벡터들:")
    for i, vec in enumerate(vectors, 1):
        print(f"  벡터 {i}: [{vec[0]:8.3f}, {vec[1]:8.3f}, {vec[2]:8.3f}]")

def extract_metal_surface_vectors(pdb_file, output_file=None):
    """금속 표면에서 벡터 추출"""
    if output_file is None:
        base_name = os.path.splitext(os.path.basename(pdb_file))[0]
        output_file = f"../input/surfaces/{base_name}.surf"
    
    print(f"PDB 파일 분석: {pdb_file}")
    
    # 원자 좌표 읽기
    atoms = read_pdb_coordinates(pdb_file)
    if len(atoms) == 0:
        print("PDB 파일에서 원자를 찾을 수 없습니다.")
        return None
    
    print(f"총 {len(atoms)}개 원자 발견")
    
    # 원소별 분포 확인
    elements = defaultdict(int)
    for atom in atoms:
        elements[atom[3]] += 1
    
    print("원소 분포:")
    for elem, count in elements.items():
        print(f"  {elem}: {count}개")
    
    # 표면 분석
    center, normal, eigenvecs = find_surface_plane(atoms)
    print(f"표면 중심: [{center[0]:8.3f}, {center[1]:8.3f}, {center[2]:8.3f}]")
    print(f"표면 법선: [{normal[0]:8.3f}, {normal[1]:8.3f}, {normal[2]:8.3f}]")
    
    # 격자 벡터 추출
    lattice_vectors = extract_lattice_vectors(atoms, center, normal)
    
    if len(lattice_vectors) < 3:
        # 충분한 벡터를 찾지 못한 경우 기본값 사용
        print("충분한 격자 벡터를 찾지 못했습니다. 기본 벡터를 사용합니다.")
        lattice_vectors = [
            [4.0, 0.0, 0.0],
            [0.0, 4.0, 0.0], 
            [2.0, 2.0, 0.0]
        ]
    
    # 표면 파일 생성
    create_surface_file(lattice_vectors[:3], output_file)
    
    return output_file

def process_all_surfaces():
    """모든 표면 파일 처리"""
    surfaces_dir = "../input/surfaces/"
    
    if not os.path.exists(surfaces_dir):
        print(f"표면 디렉토리가 없습니다: {surfaces_dir}")
        return
    
    pdb_files = [f for f in os.listdir(surfaces_dir) if f.endswith('.pdb')]
    
    if not pdb_files:
        print("처리할 PDB 파일이 없습니다.")
        return
    
    print(f"{len(pdb_files)}개의 표면 파일 발견:")
    
    for pdb_file in pdb_files:
        pdb_path = os.path.join(surfaces_dir, pdb_file)
        print(f"\n{'='*50}")
        extract_metal_surface_vectors(pdb_path)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 특정 파일 처리
        pdb_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        extract_metal_surface_vectors(pdb_file, output_file)
    else:
        # 모든 표면 파일 처리
        process_all_surfaces()