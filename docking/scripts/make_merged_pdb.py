#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SurfRosetta용 병합/정규화
- 체인만 교체, 좌표/잔기명은 보존
- 단백질: 수소 제거 + 불완전 잔기 제거 (N/CA/C/O 필수, GLY 아니면 CB 필수, sidechain 조각난 경우 삭제)
- 표면: 기본 CAL만 유지(옵션 가능)
- 일련번호 재할당, 고정폭 포맷
"""

import os, sys, argparse
from collections import defaultdict
from typing import List, Dict, Optional

def _strip(s): return s.rstrip("\r\n")
def _is_atom(l): return l.startswith("ATOM  ") or l.startswith("HETATM")

STD_AA = {"ALA","ARG","ASN","ASP","CYS","GLU","GLN","GLY","HIS","ILE",
          "LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"}

# --- parsing / formatting helpers ---
def _f(x, d=0.0):
    try: return float(x)
    except: return d

def infer_element(atom_name: str) -> str:
    a = atom_name.strip()
    if not a: return "  "
    if a[0].isdigit() and len(a) > 1: a = a[1:]
    if len(a) >= 2 and a[:2].isalpha() and a[1].islower():
        return a[:2].title().rjust(2)
    return a[0].upper().rjust(2)

def format_atom_name(atom_name: str, element: str) -> str:
    name = atom_name.strip() or ""
    el = element.strip()
    if (len(el) == 1) and (not (name[:1].isdigit())):
        return name.rjust(4)
    return name.ljust(4)

def parse_atom(line: str) -> Dict[str, object]:
    s = line
    try:
        record = s[0:6]
        serial = int(s[6:11].strip() or 0)
        atom_name = s[12:16]
        resname = s[17:20].strip() or "UNK"
        chain = (s[21:22] or "A")
        resseq = int((s[22:26].strip() or "1"))
        icode = s[26:27] or " "
        x = _f(s[30:38].strip() or "0.0")
        y = _f(s[38:46].strip() or "0.0")
        z = _f(s[46:54].strip() or "0.0")
        occ = _f(s[54:60].strip() or "1.00")
        bfac = _f(s[60:66].strip() or "0.00")
        element = s[76:78].strip() or infer_element(atom_name)
        return dict(record=record, serial=serial, atom_name=atom_name, resname=resname,
                    chain=chain, resseq=resseq, icode=icode, x=x,y=y,z=z, occ=occ,bfac=bfac,
                    element=element, charge="  ")
    except Exception:
        t = s.split()
        rec = t[0]; serial = int(t[1]) if len(t)>1 and t[1].isdigit() else 0
        an = t[2] if len(t)>2 else "X"
        rn = t[3] if len(t)>3 else "UNK"
        ch = t[4] if len(t)>4 else "A"
        rs = int(t[5]) if len(t)>5 and t[5].lstrip("-").isdigit() else 1
        x = _f(t[6],0.0) if len(t)>6 else 0.0
        y = _f(t[7],0.0) if len(t)>7 else 0.0
        z = _f(t[8],0.0) if len(t)>8 else 0.0
        occ = _f(t[9],1.00) if len(t)>9 else 1.00
        b = _f(t[10],0.00) if len(t)>10 else 0.00
        el = t[11][:2] if len(t)>11 else infer_element(an)
        return dict(record=rec, serial=serial, atom_name=an, resname=rn,
                    chain=ch, resseq=rs, icode=" ", x=x,y=y,z=z, occ=occ,bfac=b,
                    element=el, charge="  ")

def fmt_atom(d: Dict[str, object], serial: int) -> str:
    record = str(d["record"])[:6]
    atom_name = str(d["atom_name"])
    resname = str(d["resname"])[:3]
    chain = str(d["chain"])[:1] or "A"
    resseq = int(d["resseq"])
    icode = str(d.get("icode"," ") or " ")[:1]
    x = float(d["x"]); y = float(d["y"]); z = float(d["z"])
    occ = float(d.get("occ",1.00)); bfac = float(d.get("bfac",0.00))
    element = (str(d.get("element","")).strip() or infer_element(atom_name).strip())[:2]
    atom_name_f = format_atom_name(atom_name.strip(), element)
    return (f"{record}{serial:5d} {atom_name_f} {resname:>3s} {chain}"
            f"{resseq:4d}{icode}   {x:8.3f}{y:8.3f}{z:8.3f}"
            f"{occ:6.2f}{bfac:6.2f}          {element.rjust(2)}  ")

# --- IO ---
def read_atoms(path: str, chain_id: Optional[str]) -> List[Dict[str, object]]:
    out = []
    with open(path, "r") as f:
        for raw in f:
            if not _is_atom(raw): continue
            d = parse_atom(_strip(raw))
            if chain_id: d["chain"] = chain_id[:1]
            out.append(d)
    return out

def is_hydrogen(d: Dict[str, object]) -> bool:
    el = str(d.get("element","")).strip().upper()
    if not el:
        el = infer_element(str(d["atom_name"])).strip().upper()
    return el == "H"

# --- protein sanitization ---
SIDECHAIN_TREE = {
    # 최소 의존성: 부모가 없는데 자식만 있으면 드랍
    # (가벼운 검증: CB 없는데 CG/OG/SG 등 존재 → 드랍)
    "CB": [],
    "CG": ["CB"],
    "OG": ["CB"], "OG1": ["CB"], "SG": ["CB"],
    "CD": ["CG"], "ND1": ["CG"], "CD1":["CG"], "CD2":["CG"],
    "CE": ["CD"], "NE":["CD"], "NE2":["CD"], "OE1":["CD"], "OE2":["CD"],
    # 더 적을 수도 있지만 핵심은 CB/CG 의존만 보자
}

def sanitize_protein(atoms: List[Dict[str, object]],
                     strip_h: bool=True,
                     require_O: bool=True,
                     require_CB: bool=True,
                     prune_dangling: bool=True) -> List[Dict[str, object]]:
    if strip_h:
        atoms = [a for a in atoms if not is_hydrogen(a)]

    # 잔기별 그룹
    byres = defaultdict(list)
    for a in atoms:
        if a["record"].startswith("ATOM"):
            byres[(a["chain"], a["resseq"], a.get("icode"," "), a["resname"])].append(a)

    keep_keys = []
    for key, group in byres.items():
        resname = key[3]
        names = {str(g["atom_name"]).strip() for g in group}

        # 백본 완전성
        if not {"N","CA","C"}.issubset(names): 
            continue
        if require_O and "O" not in names:
            continue

        # GLY 아니면 CB 필요
        if require_CB and (resname != "GLY") and ("CB" not in names):
            continue

        # sidechain dangling(부모 없이 자식만 있는) 검출
        if prune_dangling:
            ok = True
            for n in names:
                parent = SIDECHAIN_TREE.get(n)
                if parent:
                    for p in parent:
                        if p not in names:
                            ok = False
                            break
                if not ok: break
            if not ok: 
                continue

        keep_keys.append(key)

    keepset = set(keep_keys)
    return [a for a in atoms if a["record"].startswith("ATOM") and
            (a["chain"],a["resseq"],a.get("icode"," "),a["resname"]) in keepset]

# --- surface sanitization ---
def sanitize_surface(atoms: List[Dict[str, object]], cal_only: bool=True) -> List[Dict[str, object]]:
    if not cal_only:
        return atoms
    return [a for a in atoms if str(a["resname"]).strip().upper()=="CAL"]

def serialise(atoms: List[Dict[str, object]], start: int=1) -> List[str]:
    out, s = [], start
    for a in atoms:
        out.append(fmt_atom(a, s)); s += 1
    return out

def merge(protein_file: Optional[str], surface_file: Optional[str], output: str,
          protein_chain="A", surface_chain="B", order="surface-protein",
          serial_start=1, add_ter=False, cal_only=True) -> None:
    prot = read_atoms(protein_file, protein_chain) if protein_file else []
    surf = read_atoms(surface_file, surface_chain) if surface_file else []

    if prot:
        prot = sanitize_protein(prot, strip_h=True, require_O=True, require_CB=True, prune_dangling=True)
    if surf:
        surf = sanitize_surface(surf, cal_only=cal_only)

    merged = (surf + prot) if order=="surface-protein" else (prot + surf)
    lines = serialise(merged, serial_start)

    d = os.path.dirname(output)
    if d: os.makedirs(d, exist_ok=True)
    with open(output, "w") as f:
        if add_ter and prot and surf:
            split = len(surf) if order=="surface-protein" else len(prot)
            for i,L in enumerate(lines):
                f.write(L+"\n")
                if i+1==split: f.write("TER\n")
        else:
            for L in lines: f.write(L+"\n")
        f.write("END\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-p","--protein")
    ap.add_argument("-s","--surface")
    ap.add_argument("-o","--output", required=True)
    ap.add_argument("--protein-chain", default="A")
    ap.add_argument("--surface-chain", default="B")
    ap.add_argument("--order", choices=["surface-protein","protein-surface"], default="surface-protein")
    ap.add_argument("--serial-start", type=int, default=1)
    ap.add_argument("--add-ter", action="store_true")
    ap.add_argument("--keep-all-surface", action="store_true", help="CAL만 남기는 기본 동작을 끄기")
    args = ap.parse_args()

    if not args.protein and not args.surface:
        print("[ERROR] -p 또는 -s 중 하나는 필요합니다"); sys.exit(1)

    merge(args.protein, args.surface, args.output,
          protein_chain=args.protein_chain, surface_chain=args.surface_chain,
          order=args.order, serial_start=args.serial_start, add_ter=args.add_ter,
          cal_only=(not args.keep_all_surface))

if __name__ == "__main__":
    main()