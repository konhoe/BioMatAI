#!/usr/bin/env bash
# Centroid params 생성 스크립트

PARAMS_DIR="../params"

# TI4 centroid params
cat > "$PARAMS_DIR/TI4_centroid.params" << 'EOF'
NAME TI4
IO_STRING TI4 Z
TYPE LIGAND
AA UNK
CENTROID

ATOM TI CAbb X 4.00

NBR_ATOM TI
NBR_RADIUS 2.0

ICOOR_INTERNAL TI 0.0 0.0 0.0 TI TI TI
EOF

# PSF centroid params
cat > "$PARAMS_DIR/PSF_centroid.params" << 'EOF'
NAME PSF
IO_STRING PSF X
TYPE LIGAND
AA UNK
CENTROID

ATOM P Phos X 0.00

NBR_ATOM P
NBR_RADIUS 2.0

ICOOR_INTERNAL P 0.0 0.0 0.0 P P P
EOF

echo "Centroid params 생성 완료:"
echo "  - TI4_centroid.params"
echo "  - PSF_centroid.params"