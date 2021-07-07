#!/usr/bin/env bash
if [[ -z $CONDA ]]; then
  echo "Error: no CONDA environment variable is set" 1>&2
  exit 5
fi

MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
wget $MINICONDA_URL
MINICONDA_SH="Miniconda3-latest-Linux-x86_64.sh"
sudo bash $MINICONDA_SH -b -p $CONDA
rm $MINICONDA_SH # Clean up after installing
