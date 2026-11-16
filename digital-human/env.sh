# Environment for the digital-human pipeline. Override any of these before sourcing.
# S    : a scratch folder that holds the Python venv (bpy 5.3) and the extracted MakeHuman data
# DH_MPFB : MakeHuman / MPFB2 data folder (comes inside the `anny` wheel from PyPI: anny/data/mpfb2)
# DH_WORK : intermediate .blend files and preview renders
S=${S:-/tmp/claude-0/-home-user-Ansh-Srivastava-/f60da139-88ba-5db2-9a71-f4b618aac2a6/scratchpad}
export DH_MPFB=${DH_MPFB:-$S/anny/anny/data/mpfb2}
export DH_WORK=${DH_WORK:-$S/work}
PY=${PY:-$S/venv/bin/python}
