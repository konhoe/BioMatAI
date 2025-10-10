#!/usr/bin/env python3
"""
표면 벡터 (.surf) 파일 생성기
usage: python generate_surface_vectors.py --surface TiO2 --face 110 --output surfaces/
"""
import os
import argparse
import numpy as np
from pathlib import Path

# 결정 구조 데이터베이스 (격자 상수, Angstrom 단위)
CRYSTAL_DATABASE = {
    'TiO2': {
        'rutile': {
            'a': 4.593, 'b': 4.593, 'c': 2.958,
            'alpha': 90, 'beta': 90, 'gamma': 90,
            'space_group': 'P42/mnm',
            'faces': {
                '110': {'description': 'Most stable surface', 'vectors': [[6.495, 0, 0], [0, 2.958, 0]]},
                '100': {'description': 'Less stable', 'vectors': [[4.593, 0, 0], [0, 2.958, 0]]},
                '001': {'description': 'High energy', 'vectors': [[4.593, 0, 0], [0, 4.593, 0]]}
            }
        },
        'anatase': {
            'a': 3.784, 'b': 3.784, 'c': 9.515,
            'alpha': 90, 'beta': 90, 'gamma': 90,
            'space_group': 'I41/amd',
            'faces': {
                '101': {'description': 'Most stable surface', 'vectors': [[5.351, 0, 0], [0, 3.784, 0]]},
                '100': {'description': 'Less common', 'vectors': [[3.784, 0, 0], [0, 9.515, 0]]},
                '001': {'description': 'High energy', 'vectors': [[3.784, 0, 0], [0, 3.784, 0]]}
            }
        }
    },
    'CaCO3': {
        'calcite': {
            'a': 4.990, 'b': 4.990, 'c': 17.061,
            'alpha': 90, 'beta': 90, 'gamma': 120,
            'space_group': 'R-3c',
            'faces': {
                '104': {'description': 'Cleavage surface', 'vectors': [[4.990, 0, 0], [0, 8.640, 0]]},
                '110': {'description': 'Step surface', 'vectors': [[4.990, 0, 0], [0, 17.061, 0]]},
                '012': {'description': 'High index', 'vectors': [[4.990, 0, 0], [0, 4.320, 0]]}
            }
        }
    },
    'HAP': {  # Hydroxyapatite Ca10(PO4)6(OH)2
        'hexagonal': {
            'a': 9.432, 'b': 9.432, 'c': 6.881,
            'alpha': 90, 'beta': 90, 'gamma': 120,
            'space_group': 'P63/m',
            'faces': {
                '001': {'description': 'Basal plane', 'vectors': [[9.432, 0, 0], [0, 8.173, 0]]},
                '100': {'description': 'Prismatic', 'vectors': [[8.173, 0, 0], [0, 6.881, 0]]},
                '110': {'description': 'Less common', 'vectors': [[4.716, 0, 0], [0, 6.881, 0]]}
            }
        }
    },
    'ZnO': {
        'wurtzite': {
            'a': 3.249, 'b': 3.249, 'c': 5.206,
            'alpha': 90, 'beta': 90, 'gamma': 120,
            'space_group': 'P63mc',
            'faces': {
                '0001': {'description': 'Polar Zn-terminated', 'vectors': [[3.249, 0, 0], [0, 2.814, 0]]},
                '000-1': {'description': 'Polar O-terminated', 'vectors': [[3.249, 0, 0], [0, 2.814, 0]]},
                '10-10': {'description': 'Non-polar', 'vectors': [[2.814, 0, 0], [0, 5.206, 0]]}
            }
        }
    },
    'SiO2': {
        'quartz': {
            'a': 4.913, 'b': 4.913, 'c': 5.405,
            'alpha': 90, 'beta': 90, 'gamma': 120,
            'space_group': 'P3221',
            'faces': {
                '0001': {'description': 'Basal plane', 'vectors': [[4.913, 0, 0], [0, 4.258, 0]]},
                '10-10': {'description': 'Prismatic', 'vectors': [[4.258, 0, 0], [0, 5.405, 0]]},
                '10-11': {'description': 'Pyramidal', 'vectors': [[4.258, 0, 0], [0, 4.501, 0]]}
            }
        }
    }
}

def calculate_surface_vectors(surface_material, crystal_phase, face, center_point=[0, 0, 0]):
    """표면 벡터 계산"""
    
    if surface_material not in CRYSTAL_DATABASE:
        raise ValueError(f"지원하지 않는 표면 재료: {surface_material}")
    
    phases = CRYSTAL_DATABASE[surface_material]
    if crystal_phase not in phases:
        available_phases = list(phases.keys())
        raise ValueError(f"{surface_material}의 사용 가능한 결정상: {available_phases}")
    
    phase_data = phases[crystal_phase]
    if face not in phase_data['faces']:
        available_faces = list(phase_data['faces'].keys())
        raise ValueError(f"{surface_material} {crystal_phase}의 사용 가능한 면: {available_faces}")
    
    face_data = phase_data['faces'][face]
    vectors = face_data['vectors']
    
    # 표면 벡터 생성
    surface_vectors = [
        center_point,  # 표면 중심점
        [center_point[0] + vectors[0][0], center_point[1] + vectors[0][1], center_point[2] + vectors[0][2]],  # 첫 번째 벡터
        [center_point[0] + vectors[1][0], center_point[1] + vectors[1][1], center_point[2] + vectors[1][2]]   # 두 번째 벡터
    ]
    
    return surface_vectors, face_data['description']

def create_surface_vector_file(surface_material, crystal_phase, face, output_dir="surfaces", center_point=None):
    """표면 벡터 파일 생성"""
    
    if center_point is None:
        center_point = [0.0, 0.0, 0.0]
    
    # 벡터 계산
    vectors, description = calculate_surface_vectors(surface_material, crystal_phase, face, center_point)
    
    # 파일명 생성
    filename = f"{surface_material}_{crystal_phase}_{face}.surf"
    filepath = Path(output_dir) / filename
    
    # 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    # .surf 파일 내용 생성
    surf_content = f"""# Surface vectors for {surface_material} {crystal_phase} ({face}) surface
# {description}
# Generated by generate_surface_vectors.py
# Format: x y z coordinates for center point and two unit cell vectors
"""
    
    for i, vector in enumerate(vectors):
        if i == 0:
            surf_content += f"# Center point\n"
        else:
            surf_content += f"# Vector {i}\n"
        surf_content += f"{vector[0]:8.3f} {vector[1]:8.3f} {vector[2]:8.3f}\n"
    
    # 파일 쓰기
    with open(filepath, 'w') as f:
        f.write(surf_content)
    
    print(f"[SUCCESS] {filename} 생성 완료: {filepath}")
    print(f"          표면: {surface_material} {crystal_phase} ({face})")
    print(f"          설명: {description}")
    
    return str(filepath)

def list_available_surfaces():
    """사용 가능한 표면들 목록 출력"""
    print("=== 사용 가능한 표면 재료 ===")
    
    for material, phases in CRYSTAL_DATABASE.items():
        print(f"\n{material}:")
        for phase, data in phases.items():
            print(f"  {phase} (격자상수: a={data['a']:.3f}, b={data['b']:.3f}, c={data['c']:.3f})")
            for face, face_data in data['faces'].items():
                print(f"    - {face}: {face_data['description']}")

def calculate_surface_area(surface_material, crystal_phase, face):
    """단위셀 표면적 계산"""
    try:
        vectors, _ = calculate_surface_vectors(surface_material, crystal_phase, face)
        
        # 벡터들
        v1 = np.array(vectors[1]) - np.array(vectors[0])
        v2 = np.array(vectors[2]) - np.array(vectors[0])
        
        # 외적으로 면적 계산
        cross_product = np.cross(v1, v2)
        area = np.linalg.norm(cross_product)
        
        return area
        
    except Exception as e:
        print(f"[WARNING] 면적 계산 실패: {e}")
        return None

def parse_args():
    parser = argparse.ArgumentParser(description='표면 벡터 파일 생성기')
    parser.add_argument('--surface', 
                       choices=list(CRYSTAL_DATABASE.keys()),
                       help='표면 재료')
    parser.add_argument('--phase', 
                       help='결정상 (예: rutile, anatase, calcite)')
    parser.add_argument('--face',
                       help='결정면 (예: 110, 001, 104)')
    parser.add_argument('--center', nargs=3, type=float, default=[0.0, 0.0, 0.0],
                       help='표면 중심점 좌표 (기본: 0 0 0)')
    parser.add_argument('--output', default='surfaces',
                       help='출력 디렉토리 (기본: surfaces)')
    parser.add_argument('--list', action='store_true',
                       help='사용 가능한 표면들 목록 출력')
    parser.add_argument('--all', action='store_true',
                       help='모든 표면-면 조합 생성')
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 목록 출력
    if args.list:
        list_available_surfaces()
        return 0
    
    created_files = []
    
    try:
        if args.all:
            # 모든 조합 생성
            for material, phases in CRYSTAL_DATABASE.items():
                for phase, data in phases.items():
                    for face in data['faces'].keys():
                        filepath = create_surface_vector_file(
                            material, phase, face, args.output, args.center
                        )
                        created_files.append(filepath)
                        
                        # 면적 정보 출력
                        area = calculate_surface_area(material, phase, face)
                        if area:
                            print(f"          단위셀 면적: {area:.2f} Ų")
        
        elif args.surface and args.phase and args.face:
            # 특정 표면 생성
            filepath = create_surface_vector_file(
                args.surface, args.phase, args.face, args.output, args.center
            )
            created_files.append(filepath)
            
            # 면적 정보 출력
            area = calculate_surface_area(args.surface, args.phase, args.face)
            if area:
                print(f"          단위셀 면적: {area:.2f} Ų")
        
        else:
            print("[ERROR] --surface, --phase, --face를 모두 지정하거나 --all 옵션을 사용하세요.")
            print("        --list 옵션으로 사용 가능한 표면들을 확인할 수 있습니다.")
            return 1
        
        # 요약 출력
        if created_files:
            print(f"\n[INFO] 총 {len(created_files)}개 표면 벡터 파일 생성 완료")
            print(f"       출력 디렉토리: {args.output}")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())