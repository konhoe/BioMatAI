from ase.io import read
from ase.visualize.plot import plot_atoms
import matplotlib.pyplot as plt

# CIF 파일 읽기
slab = read("Ti_0001_slab.cif")

# XY 평면에서 본 slab (z축 위로 vacuum 확인 가능)
fig, ax = plt.subplots(figsize=(6,6))
plot_atoms(slab, ax=ax, radii=0.4, rotation=('0x,0y,0z'), show_unit_cell=1)
plt.show()
