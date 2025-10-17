# merge_pdb.py
import os
import sys

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
    if len(sys.argv) != 3:
        print("Usage: python merging.py <slab_file> <protein_file>")
        sys.exit(1)

    slab_file = sys.argv[1]
    protein_file = sys.argv[2]

    # Extract metal name from slab_file path, e.g. fix_Ti.pdb -> Ti
    slab_basename = os.path.basename(slab_file)
    metal_name = slab_basename.split('_')[1].split('.')[0]

    # Extract protein name from protein_file path, e.g. albumin_A_0001.pdb -> albumin
    protein_basename = os.path.basename(protein_file)
    protein_name = protein_basename.split('_')[0]

    # Build output file path
    output_file = f"../input/merge_pdb/merged_{protein_name}_{metal_name}.pdb"

    merge_pdb(slab_file, protein_file, output_file)