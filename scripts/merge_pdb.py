#!/usr/bin/env python3
import sys, os

REC_ATOM = ("ATOM  ",)
REC_ANY  = ("ATOM  ","HETATM")

def renumber_and_set_chain(lines, chain, start_serial=1, records=REC_ANY):
    out = []
    serial = start_serial
    for ln in lines:
        if not ln.startswith(records): 
            continue
        if len(ln) < 80:
            ln = ln.rstrip("\n").ljust(80)  # 최소 폭 보정
        # serial (cols 7-11), chainID (col 22)
        ln = f"{ln[:6]}{serial:5d}{ln[11:21]}{chain}{ln[22:]}"
        out.append(ln.rstrip())
        serial += 1
    if out and not out[-1].startswith("TER"):
        out.append("TER")
    return out, serial

def read_lines(p): 
    with open(p, "r") as f: 
        return f.readlines()

def merge(prot_pdb, surf_pdb, out_pdb):
    prot = read_lines(prot_pdb)
    surf = read_lines(surf_pdb)

    chainA, next_serial = renumber_and_set_chain(prot, "A", 1, records=REC_ATOM)
    chainB, _          = renumber_and_set_chain(surf, "B", next_serial, records=REC_ANY)

    with open(out_pdb, "w") as fh:
        fh.write("REMARK merged by merge_pdb.py (A=protein, B=surface)\n")
        for l in chainA: fh.write(l + "\n")
        for l in chainB: fh.write(l + "\n")
        fh.write("END\n")

def main():
    if len(sys.argv) != 4:
        print("Usage: merge_pdb.py protein.pdb surface.pdb output.pdb")
        sys.exit(1)
    prot, surf, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    if outp.endswith("/") or os.path.isdir(outp):
        print("ERROR: output must be a .pdb file, not a directory")
        sys.exit(2)
    merge(prot, surf, outp)
    print(f"OK: wrote {outp}")

if __name__ == "__main__":
    main()