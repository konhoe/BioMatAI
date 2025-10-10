# merge_pdb.py
def merge_pdb(slab_file, protein_file, output_file):
    with open(slab_file, "r") as f1, open(protein_file, "r") as f2:
        slab_lines = f1.readlines()
        prot_lines = f2.readlines()

    merged = []

    # slab 파트: END, TER 같은 건 빼고 atom/hetatm만 남김
    for line in slab_lines:
        if line.startswith(("ATOM", "HETATM")):
            merged.append(line)

    # protein 파트도 마찬가지
    for line in prot_lines:
        if line.startswith(("ATOM", "HETATM", "SSBOND")):
            merged.append(line)

    # 마지막에 END 붙이기
    merged.append("END\n")

    with open(output_file, "w") as f:
        f.writelines(merged)

    print(f"[OK] merged pdb saved to {output_file}")


if __name__ == "__main__":
    slab_file = "../input/metal/Ti/fix_Ti.pdb"           # 금속 slab 파일
    protein_file = "../output_relax/albumin_A_0001.pdb"  # relax 끝난 단백질 파일
    output_file = "../input/merge_pdb/merged_complex.pdb"  # 최종 병합 파일

    merge_pdb(slab_file, protein_file, output_file)