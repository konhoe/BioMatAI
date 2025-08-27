import os
import time
from typing import List, Dict
import pandas as pd
from dotenv import load_dotenv

class MaterialsProjectCIFDownloader:
    def __init__(self, api_key: str):
        self.api_key = api_key
        
        # mp-api 패키지 임포트
        try:
            from mp_api.client import MPRester
            self.MPRester = MPRester
        except ImportError:
            print("ERROR: mp-api package not installed!")
            print("Please install with: pip install mp-api")
            raise
        
        # 비금속 원소들 (생체재료 관련성 고려하여 선별)
        self.nonmetals = [
            'O', 'N', 'C', 'P', 'S', 'F', 'Cl', 'Br', 'I', 'H',
            'B', 'Si', 'Se', 'Te', 'As'
        ]
        
        # 금속 원소들 (생체재료 및 합금에 자주 사용되는 것들)
        self.metals = [
            'Al', 'Mg', 'Ca', 'Zn', 'Fe', 'Co', 'Ni', 'Cu', 'Ag', 'Au',
            'Pt', 'Pd', 'Cr', 'Mo', 'W', 'V', 'Nb', 'Ta', 'Zr', 'Hf',
            'Mn', 'Re', 'Ru', 'Rh', 'Os', 'Ir', 'Sn', 'Pb', 'Bi', 'Sb'
        ]

    def search_materials_by_chemsys(self, element1: str, element2: str, limit: int = 50) -> List[Dict]:
        """
        화학 시스템으로 재료 검색 (새로운 mp-api 사용)
        """
        try:
            with self.MPRester(self.api_key) as mpr:
                # chemsys로 검색
                docs = mpr.materials.summary.search(
                    chemsys=f"{element1}-{element2}",
                    num_elements=(2, 2),  # 정확히 2원소만
                    fields=["material_id", "formula_pretty", "formation_energy_per_atom", 
                           "band_gap", "density", "total_magnetization", "structure"]
                )
                
                print(f"    Found {len(docs)} binary compounds in {element1}-{element2} system")
                return docs[:limit]
                
        except Exception as e:
            print(f"    Error searching {element1}-{element2} system: {e}")
            return []

    def save_cif_structure(self, material_id: str, structure, formula: str, folder: str) -> str:
        """
        구조를 CIF 파일로 저장
        """
        try:
            # 파일명에서 특수문자 제거
            safe_formula = formula.replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"{folder}/{material_id}_{safe_formula}.cif"
            
            # CIF 형태로 저장
            structure.to(fmt="cif", filename=filename)
            return filename
            
        except Exception as e:
            print(f"    Error saving CIF for {material_id}: {e}")
            return ""

    def download_ti_nonmetal_compounds(self, max_per_element: int = 15, total_max: int = 100):
        """
        Ti-비금속 화합물 다운로드
        """
        print("=== Downloading Ti-Nonmetal Compounds ===")
        ti_nonmetal_data = []
        total_downloaded = 0
        
        os.makedirs("cif_files/ti_nonmetals", exist_ok=True)
        
        for nonmetal in self.nonmetals:
            if total_downloaded >= total_max:
                break
                
            print(f"Searching for Ti-{nonmetal} compounds...")
            
            # mp-api로 검색
            materials = self.search_materials_by_chemsys('Ti', nonmetal, max_per_element)
            
            count = 0
            for material in materials:
                if total_downloaded >= total_max or count >= max_per_element:
                    break
                    
                material_id = material.material_id
                formula = material.formula_pretty
                structure = material.structure
                
                print(f"  Downloading {material_id} ({formula})...")
                
                # CIF 파일 저장
                filename = self.save_cif_structure(
                    material_id, structure, formula, "cif_files/ti_nonmetals"
                )
                
                if filename:
                    # 메타데이터 저장
                    ti_nonmetal_data.append({
                        'material_id': material_id,
                        'formula': formula,
                        'nonmetal_element': nonmetal,
                        'formation_energy_per_atom': material.formation_energy_per_atom,
                        'band_gap': material.band_gap,
                        'density': material.density,
                        'total_magnetization': material.total_magnetization,
                        'filename': filename
                    })
                    
                    count += 1
                    total_downloaded += 1
                    
                # API rate limit 고려
                time.sleep(0.1)
        
        # 메타데이터를 CSV로 저장
        if ti_nonmetal_data:
            df = pd.DataFrame(ti_nonmetal_data)
            df.to_csv("cif_files/ti_nonmetals_metadata.csv", index=False)
            print(f"Downloaded {len(ti_nonmetal_data)} Ti-nonmetal compounds")
        
        return ti_nonmetal_data

    def download_ti_metal_compounds(self, max_per_element: int = 15, total_max: int = 100):
        """
        Ti-금속 화합물 다운로드
        """
        print("=== Downloading Ti-Metal Compounds ===")
        ti_metal_data = []
        total_downloaded = 0
        
        os.makedirs("cif_files/ti_metals", exist_ok=True)
        
        for metal in self.metals:
            if total_downloaded >= total_max:
                break
                
            print(f"Searching for Ti-{metal} compounds...")
            
            # mp-api로 검색
            materials = self.search_materials_by_chemsys('Ti', metal, max_per_element)
            
            count = 0
            for material in materials:
                if total_downloaded >= total_max or count >= max_per_element:
                    break
                    
                material_id = material.material_id
                formula = material.formula_pretty
                structure = material.structure
                
                print(f"  Downloading {material_id} ({formula})...")
                
                # CIF 파일 저장
                filename = self.save_cif_structure(
                    material_id, structure, formula, "cif_files/ti_metals"
                )
                
                if filename:
                    # 메타데이터 저장
                    ti_metal_data.append({
                        'material_id': material_id,
                        'formula': formula,
                        'metal_element': metal,
                        'formation_energy_per_atom': material.formation_energy_per_atom,
                        'band_gap': material.band_gap,
                        'density': material.density,
                        'total_magnetization': material.total_magnetization,
                        'filename': filename
                    })
                    
                    count += 1
                    total_downloaded += 1
                    
                # API rate limit 고려
                time.sleep(0.1)
        
        # 메타데이터를 CSV로 저장
        if ti_metal_data:
            df = pd.DataFrame(ti_metal_data)
            df.to_csv("cif_files/ti_metals_metadata.csv", index=False)
            print(f"Downloaded {len(ti_metal_data)} Ti-metal compounds")
        
        return ti_metal_data

    def test_api_connection(self):
        """
        API 연결 테스트 (새로운 mp-api 사용)
        """
        try:
            with self.MPRester(self.api_key) as mpr:
                # TiO2 검색으로 테스트
                docs = mpr.materials.summary.search(
                    formula="TiO2", 
                    fields=["material_id", "formula_pretty"]
                )
                
                print(f"API Test - Found {len(docs)} results for TiO2")
                if docs:
                    print(f"API Test - Sample result: {docs[0].material_id} ({docs[0].formula_pretty})")
                    return True
                else:
                    print("API Test - No results found")
                    return False
                    
        except Exception as e:
            print(f"API Test - Exception: {e}")
            return False

    def run_download(self):
        """
        전체 다운로드 실행
        """
        print("Starting Materials Project CIF download using mp-api...")
        print(f"API Key: {self.api_key[:10]}...")
        
        # API 연결 테스트
        if not self.test_api_connection():
            print("API connection failed. Please check your API key and mp-api installation.")
            return [], []
        
        # Ti-비금속 화합물 다운로드 (100개)
        ti_nonmetal_data = self.download_ti_nonmetal_compounds(total_max=100)
        
        # Ti-금속 화합물 다운로드 (100개)  
        ti_metal_data = self.download_ti_metal_compounds(total_max=100)
        
        print("\n=== Download Summary ===")
        print(f"Ti-Nonmetal compounds: {len(ti_nonmetal_data)}")
        print(f"Ti-Metal compounds: {len(ti_metal_data)}")
        print(f"Total downloaded: {len(ti_nonmetal_data) + len(ti_metal_data)}")
        
        return ti_nonmetal_data, ti_metal_data

# 사용 예시
if __name__ == "__main__":
    # 필요한 라이브러리 설치 안내
    print("Required packages: mp-api, pandas, python-dotenv")
    print("Install with: pip install mp-api pandas python-dotenv")
    print()
    
    # .env 파일에서 환경변수 로드
    load_dotenv()
    
    # 환경변수에서 API 키 가져오기
    API_KEY = os.getenv('MATERIALS_PROJECT_API_KEY')
    
    if not API_KEY:
        print("ERROR: MATERIALS_PROJECT_API_KEY not found in environment variables!")
        print("Please check your .env file contains: MATERIALS_PROJECT_API_KEY=your_api_key_here")
        exit(1)
    
    downloader = MaterialsProjectCIFDownloader(API_KEY)
    ti_nonmetal_data, ti_metal_data = downloader.run_download()