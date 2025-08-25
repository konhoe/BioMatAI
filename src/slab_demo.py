import os
import math
from dotenv import load_dotenv
from mp_api.client import MPRester
from pymatgen.core.structure import Structure  # 빠져있던 import 구문 추가
from pymatgen.core.surface import SlabGenerator

# 0) .env에서 키 로드
load_dotenv()
MP_API_KEY = os.environ.get("MATERIALS_PROJECT_API_KEY")
if not MP_API_KEY:
    raise RuntimeError(
        "환경변수 MATERIALS_PROJECT_API_KEY가 비어 있습니다. "
        ".env에 MATERIALS_PROJECT_API_KEY=... 를 넣어주세요."
    )

# Miller Index 설정
MILLER_INDEX = (0, 0, 1)

# 출력 경로 설정 (원하는 대로 바꾸세요)
CIF_DIR = "../data/slab_data"
PROC_DIR = "../data/processed"
os.makedirs(CIF_DIR, exist_ok=True)
os.makedirs(PROC_DIR, exist_ok=True)


def create_slab_files(material_id: str, bulk_structure: Structure):
    """
    주어진 material_id와 구조(structure)에 대해 slab을 생성하고 관련 파일들을 저장하는 함수
    """
    try:
        print(f"--- {material_id} 처리 시작 ---")

        # 1) 전달받은 구조를 바로 사용 (API 중복 호출 방지)
        bulk = bulk_structure
        formula = bulk.composition.reduced_formula

        # 2) Slab 생성
        sg = SlabGenerator(
            initial_structure=bulk,
            miller_index=MILLER_INDEX,
            min_slab_size=25.0,
            min_vacuum_size=20.0,
            center_slab=True,
            in_unit_planes=True,
        )
        slabs = sg.get_slabs()
        if not slabs:
            print(f"경고: {material_id}에 대해 ({''.join(map(str, MILLER_INDEX))}) 면의 slab을 생성할 수 없습니다.")
            return

        slab = slabs[0]

        # 3) (선택) MD 대비: lateral(가로/세로) 크기 확장
        def to_nm(ang):
            return ang / 10.0

        a_nm, b_nm = to_nm(slab.lattice.a), to_nm(slab.lattice.b)
        target_nm = 6.0
        na = max(1, math.ceil(target_nm / a_nm))
        nb = max(1, math.ceil(target_nm / b_nm))
        if na > 1 or nb > 1:
            slab.make_supercell([[na, 0, 0], [0, nb, 0], [0, 0, 1]])

        # 4) 바닥 1/3 고정층 마스크
        zs = [s.frac_coords[2] for s in slab.sites]
        z_thr = sorted(zs)[int(len(zs) * 0.33)]
        freeze_idx = [i for i, z in enumerate(zs) if z <= z_thr]

        # 파일 이름에 재료 ID와 밀러 인덱스를 포함하도록 수정
        miller_str = "".join(map(str, MILLER_INDEX))
        base_filename = f"{material_id}_{miller_str}"

        freeze_path = os.path.join(PROC_DIR, f"{base_filename}_freeze_idx.txt")
        with open(freeze_path, "w") as f:
            f.write(" ".join(map(str, freeze_idx)))

        # 5) 파일 저장
        cif_path = os.path.join(CIF_DIR, f"{base_filename}_slab.cif")
        poscar_path = os.path.join(PROC_DIR, f"POSCAR_{base_filename}")
        slab.to(fmt="cif", filename=cif_path)
        slab.to(fmt="poscar", filename=poscar_path)

        print(f"✅ {material_id} ({formula}) 처리 완료:")
        print(f" - CIF     : {cif_path}")
        print(f" - POSCAR  : {poscar_path}")
        print(f" - Freeze  : {freeze_path}")

    except Exception as e:
        print(f"❌ 오류: {material_id} 처리 중 문제가 발생했습니다: {e}")


# --- 메인 실행 부분 ---
if __name__ == "__main__":
    # --- 검색하고 싶은 화학 시스템 목록 (이 부분을 수정해서 사용해!) ---
    CHEMICAL_SYSTEMS = ["Ti-O", "Ti-N", "Ti-F", "Ti-Cl", "Ti-Br", "Ti-I", "Ti-B"]

    with MPRester(MP_API_KEY) as mpr:
        # 지정된 각 화학 시스템에 대해 반복
        for system in CHEMICAL_SYSTEMS:
            print(f"========== 화학 시스템 '{system}' 검색 시작 ==========")
            try:
                # 화학 시스템으로 재료들을 검색 (ID와 구조 정보만 가져오기)
                docs = mpr.materials.search(
                    chemsys=system, fields=["material_id", "structure"]
                )

                if not docs:
                    print(f"'{system}' 시스템에 해당하는 재료를 찾을 수 없습니다.")
                    continue

                print(f"총 {len(docs)}개의 재료를 찾았습니다. 슬랩 생성을 시작합니다.")

                # 검색된 각 재료에 대해 슬랩 생성 함수를 호출
                for doc in docs:
                    create_slab_files(doc.material_id, bulk_structure=doc.structure)
                    print("-" * 25)

            except Exception as e:
                print(f"❌ 오류: '{system}' 시스템 처리 중 문제가 발생했습니다: {e}")

    print("\n모든 작업이 완료되었습니다.")
