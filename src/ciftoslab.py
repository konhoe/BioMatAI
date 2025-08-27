import os
import glob
from typing import List, Dict, Tuple
import pandas as pd
import numpy as np

class CIFToSlabConverter:
    def __init__(self):
        # pymatgen 임포트
        try:
            from pymatgen.core import Structure
            from pymatgen.core.surface import SlabGenerator, generate_all_slabs
            from pymatgen.io.cif import CifParser
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            from pymatgen.analysis.wulff import WulffShape
            
            self.Structure = Structure
            self.SlabGenerator = SlabGenerator
            self.generate_all_slabs = generate_all_slabs
            self.CifParser = CifParser
            self.SpacegroupAnalyzer = SpacegroupAnalyzer
            
        except ImportError:
            print("ERROR: pymatgen package not installed!")
            print("Please install with: pip install pymatgen")
            raise
    
    def load_structure_from_cif(self, cif_file: str):
        """
        CIF 파일에서 구조 로드
        """
        try:
            parser = self.CifParser(cif_file)
            structure = parser.parse_structures(primitive=True)[0]  # 첫 번째 구조 사용
            return structure
        except Exception as e:
            print(f"Error loading {cif_file}: {e}")
            return None

    def generate_slabs_for_structure(self, structure, material_id: str, formula: str, 
                                   miller_indices: List[Tuple] = None, 
                                   min_slab_size: float = 30.0, 
                                   min_vacuum_size: float = 20.0,
                                   target_surface_size: float = 60.0,  # 6nm target
                                   max_normal_search: int = 2) -> List[Dict]:
        """
        주어진 구조에서 단백질 docking용 large slab들 생성
        
        Parameters:
        - structure: pymatgen Structure 객체
        - miller_indices: Miller index 리스트 [(1,0,0), (1,1,0), (1,1,1) 등]
        - min_slab_size: 최소 slab 두께 (Angstrom) - 30Å = 3nm
        - min_vacuum_size: 진공층 두께 (Angstrom) - 20Å = 2nm
        - target_surface_size: 목표 표면 크기 (Angstrom) - 60Å = 6nm (단백질 docking용)
        - max_normal_search: Miller index 검색 범위
        """
        
        if miller_indices is None:
            # 일반적인 생체재료 연구에서 중요한 표면들
            miller_indices = [
                (1, 0, 0), (0, 1, 0), (0, 0, 1),  # 기본 면
                (1, 1, 0), (1, 0, 1), (0, 1, 1),  # 대각선 면
                (1, 1, 1), (2, 1, 0), (2, 1, 1)   # 고지수 면
            ]
        
        slab_data = []
        
        # 각 Miller index에 대해 slab 생성
        for hkl in miller_indices:
            try:
                print(f"    Generating slab for Miller index {hkl}...")
                
                # SlabGenerator 생성
                slabgen = self.SlabGenerator(
                    initial_structure=structure,
                    miller_index=hkl,
                    min_slab_size=min_slab_size,
                    min_vacuum_size=min_vacuum_size,
                    lll_reduce=True,  # 격자 벡터 최적화
                    center_slab=True,  # slab을 중앙에 배치
                    primitive=True,    # primitive cell 사용
                    max_normal_search=max_normal_search
                )
                
                # 모든 가능한 termination 생성
                slabs = slabgen.get_slabs(
                    bonds=None,  # 자동으로 결합 분석
                    symmetrize=True,  # 대칭성 적용
                    tol=0.1,
                    max_broken_bonds=2  # 최대 끊어진 결합 수
                )
                
                for i, slab in enumerate(slabs):
                    # 단백질 docking을 위한 supercell 생성
                    supercell_slab = self.create_protein_docking_supercell(
                        slab, target_surface_size
                    )
                    
                    # Surface energy 계산 (간단한 추정)
                    try:
                        # SlabGenerator에서 직접 속성 접근
                        surface_energy = None  # 간단화
                    except:
                        surface_energy = None
                    
                    # 실제 표면 크기 계산
                    actual_surface_area = (supercell_slab.lattice.matrix[0][0] * 
                                         supercell_slab.lattice.matrix[1][1])
                    
                    # Slab 정보 저장
                    slab_info = {
                        'material_id': material_id,
                        'formula': formula,
                        'miller_index': f"{hkl[0]}{hkl[1]}{hkl[2]}",
                        'termination': i,
                        'num_layers': len(slab),
                        'slab_thickness': min_slab_size,
                        'vacuum_thickness': min_vacuum_size,
                        'surface_area': actual_surface_area,
                        'surface_length_a': supercell_slab.lattice.matrix[0][0],
                        'surface_length_b': supercell_slab.lattice.matrix[1][1],
                        'num_atoms': len(supercell_slab),
                        'is_supercell': True,
                        'surface_energy': surface_energy,
                        'is_symmetric': supercell_slab.is_symmetric(),
                        'slab_structure': supercell_slab
                    }
                    
                    slab_data.append(slab_info)
                    print(f"      Created supercell: {slab_info['surface_length_a']:.1f} × {slab_info['surface_length_b']:.1f} Å ({slab_info['num_atoms']} atoms)")
                    
            except Exception as e:
                print(f"      Error generating slab for {hkl}: {e}")
                continue
        
        return slab_data

    def create_protein_docking_supercell(self, slab, target_size: float = 60.0):
        """
        단백질 docking에 적합한 크기의 supercell 생성
        
        Parameters:
        - slab: 원본 slab 구조
        - target_size: 목표 표면 크기 (Angstrom)
        """
        # 현재 lattice parameter
        a = slab.lattice.matrix[0][0]  # a축 길이
        b = slab.lattice.matrix[1][1]  # b축 길이
        
        # 필요한 반복 횟수 계산
        repeat_a = max(1, int(np.ceil(target_size / a)))
        repeat_b = max(1, int(np.ceil(target_size / b)))
        
        print(f"        Creating {repeat_a}×{repeat_b}×1 supercell (target: {target_size}Å)")
        
        # Supercell 생성
        supercell = slab.copy()
        supercell.make_supercell([repeat_a, repeat_b, 1])
        
        return supercell

    def save_slab_structures(self, slab_data: List[Dict], output_dir: str):
        """
        생성된 slab 구조들을 파일로 저장
        """
        os.makedirs(output_dir, exist_ok=True)
        
        saved_files = []
        for slab_info in slab_data:
            try:
                # 파일명 생성
                filename = f"{slab_info['material_id']}_{slab_info['formula'].replace(' ', '_')}_{slab_info['miller_index']}_term{slab_info['termination']}.cif"
                filepath = os.path.join(output_dir, filename)
                
                # CIF 파일로 저장
                slab_info['slab_structure'].to(fmt="cif", filename=filepath)
                
                # 파일 경로 정보 추가
                slab_info['slab_filename'] = filepath
                saved_files.append(filepath)
                
                print(f"      Saved slab: {filename}")
                
            except Exception as e:
                print(f"      Error saving slab {slab_info['material_id']}: {e}")
                continue
        
        return saved_files

    def analyze_surface_properties(self, slab_data: List[Dict]) -> pd.DataFrame:
        """
        표면 특성 분석
        """
        analysis_data = []
        
        for slab_info in slab_data:
            slab = slab_info['slab_structure']
            
            try:
                # 표면 원자 분석
                surface_atoms = self.identify_surface_atoms(slab)
                
                # 표면 거칠기 계산 (Z 좌표 표준편차)
                z_coords = [site.coords[2] for site in slab.sites]
                surface_roughness = np.std(z_coords)
                
                # 원자 밀도 계산
                surface_area = slab.lattice.matrix[0][0] * slab.lattice.matrix[1][1]
                surface_atom_density = len(surface_atoms) / surface_area
                
                analysis_info = {
                    'material_id': slab_info['material_id'],
                    'formula': slab_info['formula'],
                    'miller_index': slab_info['miller_index'],
                    'termination': slab_info['termination'],
                    'surface_roughness': surface_roughness,
                    'surface_atom_density': surface_atom_density,
                    'num_surface_atoms': len(surface_atoms),
                    'dominant_surface_element': self.get_dominant_surface_element(surface_atoms),
                    'coordination_numbers': self.calculate_coordination_numbers(slab, surface_atoms)
                }
                
                analysis_data.append(analysis_info)
                
            except Exception as e:
                print(f"      Error analyzing surface for {slab_info['material_id']}: {e}")
                continue
        
        return pd.DataFrame(analysis_data)

    def identify_surface_atoms(self, slab, threshold: float = 2.0):
        """
        표면 원자 식별 (Z 좌표 기준)
        """
        z_coords = [site.coords[2] for site in slab.sites]
        max_z = max(z_coords)
        min_z = min(z_coords)
        
        surface_atoms = []
        for i, site in enumerate(slab.sites):
            # 상부 및 하부 표면 원자 식별
            if (site.coords[2] > max_z - threshold) or (site.coords[2] < min_z + threshold):
                surface_atoms.append({'index': i, 'site': site})
        
        return surface_atoms

    def get_dominant_surface_element(self, surface_atoms):
        """
        표면에서 가장 많은 원소 찾기
        """
        if not surface_atoms:
            return None
        
        elements = [atom['site'].species_string for atom in surface_atoms]
        from collections import Counter
        return Counter(elements).most_common(1)[0][0]

    def calculate_coordination_numbers(self, slab, surface_atoms, cutoff: float = 3.0):
        """
        표면 원자들의 배위수 계산
        """
        coord_numbers = []
        
        for atom in surface_atoms:
            site = atom['site']
            neighbors = slab.get_neighbors(site, cutoff)
            coord_numbers.append(len(neighbors))
        
        return {
            'mean_coordination': np.mean(coord_numbers) if coord_numbers else 0,
            'min_coordination': min(coord_numbers) if coord_numbers else 0,
            'max_coordination': max(coord_numbers) if coord_numbers else 0
        }

    def process_cif_directory(self, cif_directory: str, slab_output_dir: str = "slab_files", 
                            max_files: int = None, miller_indices: List[Tuple] = None):
        """
        CIF 파일 디렉토리를 처리하여 slab 생성
        """
        print(f"Processing CIF files from {cif_directory}...")
        
        # CIF 파일 목록 가져오기
        cif_files = glob.glob(os.path.join(cif_directory, "*.cif"))
        
        if max_files:
            cif_files = cif_files[:max_files]
        
        print(f"Found {len(cif_files)} CIF files to process")
        
        all_slab_data = []
        processed_count = 0
        
        for cif_file in cif_files:
            print(f"\nProcessing {os.path.basename(cif_file)}...")
            
            # 파일명에서 material_id와 formula 추출
            basename = os.path.basename(cif_file).replace('.cif', '')
            parts = basename.split('_', 1)
            material_id = parts[0] if parts else basename
            formula = parts[1] if len(parts) > 1 else "Unknown"
            
            # 구조 로드
            structure = self.load_structure_from_cif(cif_file)
            if structure is None:
                continue
            
            # Slab 생성
            slab_data = self.generate_slabs_for_structure(
                structure, material_id, formula, miller_indices
            )
            
            if slab_data:
                # Slab 파일 저장
                material_slab_dir = os.path.join(slab_output_dir, material_id)
                saved_files = self.save_slab_structures(slab_data, material_slab_dir)
                
                all_slab_data.extend(slab_data)
                processed_count += 1
                
                print(f"  Generated {len(slab_data)} slabs for {material_id}")
        
        # 종합 분석 및 메타데이터 저장
        if all_slab_data:
            # 메타데이터 저장
            metadata_df = pd.DataFrame([
                {
                    'material_id': slab['material_id'],
                    'formula': slab['formula'],
                    'miller_index': slab['miller_index'],
                    'termination': slab['termination'],
                    'num_layers': slab['num_layers'],
                    'slab_thickness': slab['slab_thickness'],
                    'vacuum_thickness': slab['vacuum_thickness'],
                    'surface_area': slab['surface_area'],
                    'surface_energy': slab['surface_energy'],
                    'is_symmetric': slab['is_symmetric'],
                    'slab_filename': slab.get('slab_filename', '')
                }
                for slab in all_slab_data
            ])
            
            metadata_df.to_csv(f"{slab_output_dir}/slab_metadata.csv", index=False)
            
            # 표면 특성 분석
            analysis_df = self.analyze_surface_properties(all_slab_data)
            analysis_df.to_csv(f"{slab_output_dir}/surface_analysis.csv", index=False)
            
            print(f"\n=== Slab Generation Summary ===")
            print(f"Processed {processed_count} materials")
            print(f"Generated {len(all_slab_data)} slabs total")
            print(f"Saved metadata to {slab_output_dir}/slab_metadata.csv")
            print(f"Saved surface analysis to {slab_output_dir}/surface_analysis.csv")
        
        return all_slab_data

# 사용 예시
if __name__ == "__main__":
    print("CIF to Slab Converter")
    print("Required packages: pymatgen, pandas, numpy")
    print("Install with: pip install pymatgen pandas numpy")
    print()
    
    converter = CIFToSlabConverter()
    
    # Ti-nonmetal 화합물 slab 생성
    if os.path.exists("cif_files/ti_nonmetals"):
        print("Processing Ti-nonmetal compounds...")
        ti_nonmetal_slabs = converter.process_cif_directory(
            "cif_files/ti_nonmetals", 
            "slab_files/ti_nonmetals",
            max_files=20,  # 테스트용으로 20개만
            miller_indices=[(1,0,0), (1,1,0), (1,1,1)]  # 주요 면만
        )
    
    # Ti-metal 화합물 slab 생성
    if os.path.exists("cif_files/ti_metals"):
        print("\nProcessing Ti-metal compounds...")
        ti_metal_slabs = converter.process_cif_directory(
            "cif_files/ti_metals", 
            "slab_files/ti_metals",
            max_files=20,  # 테스트용으로 20개만
            miller_indices=[(1,0,0), (1,1,0), (1,1,1)]  # 주요 면만
        )
    
    print("\nSlab generation completed!")
    print("Next step: Use these slab structures for protein docking!")