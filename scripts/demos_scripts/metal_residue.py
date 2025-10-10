#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
metal_residue.py
- 입력 PDB에서 금속/표면 원소를 자동 인식
- Rosetta용 params 파일(금속, P2) 생성
- PDB 안의 HETATM 잔기명 일괄 정리(금속: TI4/MG2 등, P*: P2로 통일)
- 단백질 ATOM 레코드는 그대로 두고 HETATM만 수정

usage:
  python metal_residue.py --pdb input_surface.pdb \
                          --out-params params/ \
                          --out-pdb cleaned_surface.pdb \
                          [--charge-map TI:4,FE:2,AL:3] \
                          [--keep-resnames]   # (옵션) 리네이밍 안하고 params만 생성
"""
import re
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict

# 기본 금속 전하(필요시 --charge-map으로 오버라이드)
DEFAULT_CHARGE = {
    "TI": 4, "MG": 2, "ZN": 2, "CA": 2, "CU": 2, "NI": 2, "CO": 2, "MN": 2, "FE": 2, "AL": 3
}
# Rosetta atom type: 실전에서 Ti도 잘 동작했던 케이스가 있으므로 element 그대로 사용
# (문제되면 개별 프로젝트에서 조정)
def metal_params_text(resname:str, element:str, charge:int) -> str:
    """
    단일 금속 + 가상원자 4개(테트라) 템플릿.
    - Rosetta가 단일 원자 리간드를 다룰 때 안정적으로 돌아가도록 VIRT 보강.
    """
    element = element.upper()
    return f"""# Auto-generated metal params for {element}{charge}+
# Residue name: {resname}
NAME {resname}
IO_STRING {resname} Z
TYPE LIGAND
AA UNK
ATOM {element:<2}  {element:<4}  X   {float(charge):.2f}
ATOM V1   VIRT    X   0.00
ATOM V2   VIRT    X   0.00
ATOM V3   VIRT    X   0.00
ATOM V4   VIRT    X   0.00
BOND {element:<2} V1
BOND {element:<2} V2
BOND {element:<2} V3
BOND {element:<2} V4
NBR_ATOM {element:<2}
NBR_RADIUS 0.01
ICOOR_INTERNAL {element:<2}  0.0  0.0  0.0  {element:<2}  V1   V2
ICOOR_INTERNAL V1            0.0  0.0  2.2  {element:<2}  V1   V2
ICOOR_INTERNAL V2            0.0 70.5  2.2  {element:<2}  V1   V2
ICOOR_INTERNAL V3          120.0 70.5  2.2  {element:<2}  V1   V2
ICOOR_INTERNAL V4         -120.0 70.5  2.2  {element:<2}  V1   V2
"""

def p2_params_text() -> str:
    """
    표면 P 자리를 모두 P2로 통일해서 한 개의 단일 원자 리간드로 처리.
    (전하 0; 필요시 프로젝트에 맞게 바꿔도 됨)
    """
    return """# Auto-generated surface phosphate site (P2), neutral single-atom ligand
NAME P2
IO_STRING P2 X
TYPE LIGAND
AA UNK
ATOM P   P     X   0.00
ATOM V1  VIRT  X   0.00
ATOM V2  VIRT  X   0.00
ATOM V3  VIRT  X   0.00
ATOM V4  VIRT  X   0.00
BOND P   V1
BOND P   V2
BOND P   V3
BOND P   V4
NBR_ATOM P
NBR_RADIUS 0.01
ICOOR_INTERNAL  P   0.0   0.0   0.0   P   V1  V2
ICOOR_INTERNAL  V1  0.0   0.0   2.2   P   V1  V2
ICOOR_INTERNAL  V2  0.0  70.5   2.2   P   V1  V2
ICOOR_INTERNAL  V3 120.0 70.5   2.2   P   V1  V2
ICOOR_INTERNAL  V4-120.0 70.5   2.2   P   V1  V2
"""

def parse_args():
    ap = argparse.ArgumentParser(description="PDB에서 금속/표면 원소를 자동 인식해 params 생성 및 PDB 정리")
    ap.add_argument("--pdb", required=True, help="입력 PDB 경로 (표면/금속 포함)")
    ap.add_argument("--out-params", default="params", help="params 출력 디렉토리 (기본: params/)")
    ap.add_argument("--out-pdb", required=True, help="정리된 PDB 출력 경로")
    ap.add_argument("--charge-map", default="", help="금속 전하 오버라이드 예: 'TI:4,FE:3,AL:3'")
    ap.add_argument("--keep-resnames", action="store_true", help="잔기 리네이밍을 하지 않고 params만 생성")
    return ap.parse_args()

def parse_charge_override(s):
    d = {}
    if not s:
        return d
    for tok in s.split(","):
        tok = tok.strip()
        if not tok: continue
        k, v = tok.split(":")
        d[k.strip().upper()] = int(v.strip())
    return d

def guess_element_from_pdb_line(line:str) -> str:
    """
    PDB 고정폭 포맷 기반으로 element 추출.
    - 우선 77-78 컬럼(Element) 사용
    - 없으면 atom name에서 유추
    """
    rec = line[0:6].strip()
    if rec not in ("HETATM", "ATOM"):
        return ""
    elem = line[76:78].strip()
    if elem:
        return elem.upper()
    # fallback: atom name
    atom = line[12:16].strip()
    # 예: 'Ti10' 같은 경우 앞쪽 문자만 추출
    m = re.match(r"([A-Za-z]+)", atom)
    if m:
        return m.group(1).upper()
    return ""

def standard_resname_for_metal(elem:str, charge_map:dict) -> str:
    elem = elem.upper()
    chg = charge_map.get(elem, DEFAULT_CHARGE.get(elem))
    if chg is None:
        # 기본값이 없으면 2가 가장 무난
        chg = 2
    return f"{elem}{chg}", chg

def rewrite_pdb(in_pdb:str, out_pdb:str, charge_map:dict, do_rename:bool=True):
    """
    - HETATM만 대상으로 금속/표면 리네이밍
    - 금속: resName -> <EL><charge> (예: TI4, MG2)
      atomName -> '<EL>' (2~3글자면 왼쪽정렬)
    - P*: resName -> P2, atomName -> 'P'
    - 단백질 ATOM은 그대로 둠
    반환값: {'metals': set([...]), 'used_resnames': set([...]), 'p_count': int}
    """
    metals_found = set()
    used_resnames = set()
    p_count = 0

    with open(in_pdb, "r") as fin, open(out_pdb, "w") as fout:
        for line in fin:
            if not line.startswith(("HETATM", "ATOM")):
                fout.write(line); continue

            rec = line[0:6]
            if rec == "ATOM  ":
                # 단백질은 그대로
                fout.write(line)
                continue

            # HETATM만 처리
            elem = guess_element_from_pdb_line(line)
            resn = line[17:20]
            # 숫자 붙은 P* → P2
            if elem == "P" or re.fullmatch(r"\s*P\d\s*", resn):
                if do_rename:
                    # resName -> P2, atomName -> P
                    new_resn = "P2 "
                    new_atom = " P  "
                    line = line[:12] + f"{new_atom:4s}" + line[16:17] + f"{new_resn:3s}" + line[20:]
                p_count += 1
                used_resnames.add("P2")
                fout.write(line)
                continue

            # 금속?
            if elem in set(DEFAULT_CHARGE.keys()).union(set(charge_map.keys())):
                metals_found.add(elem)
                if do_rename:
                    std_resn, _chg = standard_resname_for_metal(elem, charge_map)
                    # resName 적용, atomName은 element로
                    new_resn = f"{std_resn:3s}"
                    # atomName은 element 대문자(최대 2~3칸)
                    atom_symbol = elem if len(elem) <= 3 else elem[:3]
                    new_atom = f"{atom_symbol:>2s}  " if len(atom_symbol) <= 2 else f"{atom_symbol:>3s} "
                    line = line[:12] + new_atom + line[16:17] + new_resn + line[20:]
                    used_resnames.add(std_resn)
                fout.write(line)
                continue

            # 그 외 HETATM은 그대로 통과
            fout.write(line)

    return {"metals": metals_found, "used_resnames": used_resnames, "p_count": p_count}

def ensure_params(params_dir:str, metals:set, used_resnames:set, charge_map:dict):
    os.makedirs(params_dir, exist_ok=True)
    written = []

    # P2가 쓰였으면 생성
    if "P2" in used_resnames:
        p2_path = Path(params_dir) / "P2.params"
        if not p2_path.exists():
            p2_path.write_text(p2_params_text())
        written.append(str(p2_path))

    # 금속 params
    for elem in sorted(metals):
        resn, chg = standard_resname_for_metal(elem, charge_map)
        out = Path(params_dir) / f"{resn}.params"
        if not out.exists():
            out.write_text(metal_params_text(resn, elem, chg))
        written.append(str(out))

    return written

def main():
    args = parse_args()
    charge_map = parse_charge_override(args.charge_map)

    # 1) PDB 리라이트(또는 스킵)
    info = rewrite_pdb(
        in_pdb=args.pdb,
        out_pdb=args.out_pdb,
        charge_map=charge_map,
        do_rename=(not args.keep_resnames)
    )

    # 2) params 생성
    written = ensure_params(
        params_dir=args.out_params,
        metals=info["metals"],
        used_resnames=info["used_resnames"],
        charge_map=charge_map
    )

    # 요약
    print("=== metal_residue.py summary ===")
    print(f"- metals found: {sorted(info['metals'])}")
    print(f"- unified residue names: {sorted(info['used_resnames'])}")
    print(f"- P sites unified to P2: {info['p_count']} atoms")
    print(f"- params written: {', '.join(Path(w).name for w in written)}")
    print(f"- cleaned PDB: {args.out_pdb}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
