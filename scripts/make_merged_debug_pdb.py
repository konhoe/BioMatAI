# scripts/make_merged_debug_pdb.py
import sys, os

prot = "../input/albumin.pdb"
surf = "../input/mp-20327_TiP2_100_term0.pdb"
outp = "../input/merged_A_B.pdb"

def fmt_hetatm(serial,x,y,z,chain='B',resseq=1,resname='ZN',elem='ZN',name='ZN'):
    # PDB 고정폭 포맷 (columns 맞춤)
    return (f"HETATM{serial:5d} {name:^4s}{resname:>3s} {chain}{resseq:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{0.00:6.2f}          {elem:>2s}")

# 1) 표면 → 깨끗한 HETATM들로 재작성
surf_lines=[]
serial=1
with open(surf) as f:
    for ln in f:
        ln=ln.strip()
        if not ln: continue
        # 좌표 파싱 (공백분리 가정; x y z 가 끝 3개 열)
        toks = ln.split()
        # 좌표 3개만 있는 경우도 지원
        if len(toks)>=3 and all(t.replace('.','',1).replace('-','',1).isdigit()==False for t in toks[:2]):
            # 이미 PDB형이면 건너뜀
            pass
        try:
            # 뒤에서 3개를 x y z로 간주
            x,y,z = map(float, toks[-3:])
        except:
            continue
        surf_lines.append(fmt_hetatm(serial,x,y,z))
        serial+=1

# 2) 단백질 ATOM/TER만 보존하고 체인=A로 강제
prot_lines=[]
with open(prot) as f:
    for ln in f:
        if ln.startswith("ATOM") or ln.startswith("TER"):
            lst=list(ln.rstrip('\n'))
            if len(lst)<80: lst += [' ']*(80-len(lst))
            # 체인ID (col 22, 0-index 21)
            lst[21]='A'
            prot_lines.append(''.join(lst))

# 3) 병합 저장 (표면 먼저, 단백질 다음)
with open(outp,"w") as w:
    w.write("REMARK merged for docking test (surface as ZN grid)\n")
    for ln in surf_lines: w.write(ln+"\n")
    for ln in prot_lines: w.write(ln+"\n")
    w.write("END\n")

print(f"wrote {outp} with {len(surf_lines)} HETATM(ZN) and {len(prot_lines)} protein lines")