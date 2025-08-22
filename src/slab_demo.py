import os, math
from dotenv import load_dotenv
from pymatgen.ext.matproj import MPRester
from pymatgen.core.surface import SlabGenerator

# 0) .env에서 키 로드
load_dotenv()
MP_API_KEY = os.environ.get("MATERIALS_PROJECT_API_KEY")
if not MP_API_KEY:
    raise RuntimeError(
        "환경변수 MATERIALS_PROJECT_API_KEY가 비어 있습니다. "
        ".env에 MATERIALS_PROJECT_API_KEY=... 를 넣어주세요."
    )

# 출력 경로 설정 (원하는 대로 바꾸세요)
CIF_DIR = "../data/slab_data"
PROC_DIR = "../data/processed"
os.makedirs(CIF_DIR, exist_ok=True)
os.makedirs(PROC_DIR, exist_ok=True)

# 1) Materials Project에서 Ti(hcp) 구조 가져오기 (mp-72는 대표 Ti hcp)
with MPRester(MP_API_KEY) as mpr:
    bulk = mpr.get_structure_by_material_id("mp-72")  # Structure 객체 반환

# 2) Slab 생성: (0001) 면, slab 두께/진공은 실무 관례 값 (2.5nm / 2.0nm 근처)
sg = SlabGenerator(
    initial_structure=bulk,
    miller_index=(0, 0, 1),   # (0001)
    min_slab_size=25.0,       # slab 두께(Å) ≈ 2.5 nm
    min_vacuum_size=20.0,     # 진공(Å)  ≈ 2.0 nm
    center_slab=True,
    in_unit_planes=True
)
slab = sg.get_slabs()[0]      # 첫 번째 slab 사용(대표 termination)

# 3) (선택) MD 대비: lateral(가로/세로) 크기 확장
def to_nm(ang): return ang / 10.0
a_nm, b_nm = to_nm(slab.lattice.a), to_nm(slab.lattice.b)
target_nm = 6.0   # Albumin 고려하면 6~8nm 권장 (계산비용 따라 조절)
na = max(1, math.ceil(target_nm / a_nm))
nb = max(1, math.ceil(target_nm / b_nm))
if na > 1 or nb > 1:
    slab.make_supercell([[na,0,0],[0,nb,0],[0,0,1]])

# 4) 바닥 1/3 고정층 마스크 (MD에서 position restraint용)
zs = [s.frac_coords[2] for s in slab.sites]
z_thr = sorted(zs)[int(len(zs) * 0.33)]
freeze_idx = [i for i, z in enumerate(zs) if z <= z_thr]
freeze_path = os.path.join(PROC_DIR, "Ti_0001_freeze_idx.txt")
with open(freeze_path, "w") as f:
    f.write(" ".join(map(str, freeze_idx)))

# 5) 파일 저장
cif_path = os.path.join(CIF_DIR, "Ti_0001_slab.cif")
poscar_path = os.path.join(PROC_DIR, "POSCAR_Ti_0001")
slab.to(fmt="cif", filename=cif_path)
slab.to(fmt="poscar", filename=poscar_path)

print("Saved:")
print(" - CIF     :", cif_path)
print(" - POSCAR  :", poscar_path)
print(" - Freeze  :", freeze_path)
