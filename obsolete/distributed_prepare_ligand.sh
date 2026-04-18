#!/bin/bash

# When dealing with less amount of molecules, use the following commands:
# for i in `ls sdf_3d`; do obabel -isdf sdf_3d/$i -omol2 -O mol2_3d/${i%.*}.mol2; done
# conda activate python2
# cd mol2_3d
# for i in `ls`; do prepare_ligand4.py -l $i -o ../pdbqt_3d/${i%.*}.pdbqt; done

export OBABEL=/public/home/caiyi/software/miniconda3/bin/obabel
export PYTHON2=/public/home/caiyi/software/miniconda3/envs/python2/bin/python2
PYTHON3=/public/home/caiyi/software/miniconda3/bin/python
export PREPARE_LIGAND4=/public/home/caiyi/software/miniconda3/envs/python2/bin/prepare_ligand4.py
CODE_PATH=/public/home/caiyi/eric_github/vs_protocol

usage() {
cat <<EOF
Prepare ligands using multiple threads. Input a single smi file which contains a lot of molecules and output a pdbqt file for each molecule. 
Requirements: OpenBabel, Python2, MGLTools. Edit variables OBABEL, PYTHON2 and PREPARE_LIGAND4 if needed.
Caution: OpenBabel version and build is critical for running speed. Better to use conda to install openbabel 2.4.1. Do not use OpenBabel 3.1.0, OpenBabel in MGLTools, or OpenBabel in AFDR Suite.

Usage: batch_prepare_ligand.sh -i <input_file> -o <output_dir> -t <number_of_threads> [-f -v]
-f: continue even if directory not empty
-v: verbose
EOF
}

[ "$1" = "" ] && usage && exit 1;

verbose=0
forced=0
while getopts "i:o:t:vfh" opt; do
    case $opt in
        i) input=$OPTARG;;
        o) output=$OPTARG;;
        t) n_threads=$OPTARG;;
        h) usage;
           exit 1;;
        v) verbose=1;;
        f) forced=1;;
        ?) echo "Wrong options!"
           exit 1;;
    esac
done

PWD=$(pwd)
input=$(readlink -f $input)
export output=$(readlink -f $output)
export WD=$(readlink -f $(dirname $input))
fn=$(basename $input)
export base=${fn%.*}

if [ ! -d $WD/${base}_mol2 ]; then
    mkdir $WD/${base}_mol2
elif [ "$(ls -A $WD/${base}_mol2)" ] && [ ! $forced -eq 1 ]; then
    echo "Directory $WD/${base}_mol2 is not empty!"
    exit 1
fi

if [ ! -d $output ]; then
    mkdir $output
elif [ "$(ls -A $output)" ] && [ ! $forced -eq 1 ]; then
    echo "Directory $output is not empty!"
    exit 1
fi

echo $PYTHON3 $CODE_PATH/parse_pbsstat.py $n_threads
# Error for bash 5; Work for bash 4
IFS=$' ' read -r -a task_array <<< $($PYTHON3 $CODE_PATH/parse_pbsstat.py $n_threads)
# Alternative
# mapfile -t task_array < <($PYTHON3 $CODE_PATH/vs_integrated/parse_pbsstat.py $n_threads)

echo parallel -S ${task_array[0]}/node1,${task_array[1]}/node2,${task_array[2]}/node3,${task_array[3]}/gpu1,${task_array[4]}/gpu2 --linebuffer --bar '
    LINE={}
    zinc=${LINE##* }
    timeout 5m '"$OBABEL"' -:"$LINE" -omol2 -O '"$WD"'/'"${base}"'_mol2/'"${base}"'_${zinc}.mol2 --gen3d > /dev/null 2>&1
    cd '"$WD"'/'"${base}"'_mol2/
    '"$PYTHON2"' '"$PREPARE_LIGAND4"' -l '"$WD"'/'"${base}"'_mol2/'"${base}"'_${zinc}.mol2 -o '"$output"'/'"${base}"'_${zinc}.pdbqt
' < $input

parallel -S ${task_array[0]}/node1,${task_array[1]}/node2,${task_array[2]}/node3,${task_array[3]}/gpu1,${task_array[4]}/gpu2 --linebuffer --bar '
    LINE={}
    zinc=${LINE##* }
    timeout 5m '"$OBABEL"' -:"$LINE" -omol2 -O '"$WD"'/'"${base}"'_mol2/'"${base}"'_${zinc}.mol2 --gen3d > /dev/null 2>&1
    cd '"$WD"'/'"${base}"'_mol2/
    '"$PYTHON2"' '"$PREPARE_LIGAND4"' -l '"$WD"'/'"${base}"'_mol2/'"${base}"'_${zinc}.mol2 -o '"$output"'/'"${base}"'_${zinc}.pdbqt
' < $input

wait

cd $PWD