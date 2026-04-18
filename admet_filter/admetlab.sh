#!/bin/bash

usage() {
cat <<EOF
Run ADMETlab prediction.

Usage: admetlab.sh -i <input_smi_file> -d <working_directory> -t <num_threads> -s <suffix>

Example: admetlab.sh -i library.smi -d . -t 50 -s tryout
EOF
}

PYTHON2=/public/home/caiyi/software/miniconda3/envs/python2/bin/python
PYTHON3=/public/home/caiyi/software/miniconda3/envs/python39/bin/python
BIN_PATH=/public/home/caiyi/eric_github/vs_protocol/module_2

[ "$1" = "" ] && usage && exit 1;

while getopts "i:d:t:s:h" opt; do
    case $opt in
        i) input=$OPTARG;;
        d) wd=$OPTARG;;
        t) threads=$OPTARG;;
        s) suffix=$OPTARG;;
        h) usage;
           exit 1;;
        ?) echo "Invalid options!"
           exit 1;;
    esac
done

fn=${input##*/}
$PYTHON3 $BIN_PATH/dedup.py -i $input -o $wd/admetlab_input_$suffix.smi
$PYTHON3 $BIN_PATH/admetlab_des.py -i $wd/admetlab_input_$suffix.smi -o $wd/des_$suffix.csv -t $threads
$PYTHON3 $BIN_PATH/gen_fp.py -i $wd/admetlab_input_$suffix.smi -o $wd/MACCS_$suffix.h5 -fp maccs_full -t $threads
$PYTHON3 $BIN_PATH/gen_fp.py -i $wd/admetlab_input_$suffix.smi -o $wd/ECFP2_2048_$suffix.h5 -fp ecfp2_2048 -t $threads
$PYTHON3 $BIN_PATH/gen_fp.py -i $wd/admetlab_input_$suffix.smi -o $wd/ECFP4_2048_$suffix.h5 -fp ecfp4_2048 -t $threads
$PYTHON3 $BIN_PATH/gen_fp.py -i $wd/admetlab_input_$suffix.smi -o $wd/ECFP4_1024_$suffix.h5 -fp ecfp4_1024 -t $threads
$PYTHON3 $BIN_PATH/gen_fp.py -i $wd/admetlab_input_$suffix.smi -o $wd/ECFP6_2048_$suffix.h5 -fp ecfp6_2048 -t $threads

$PYTHON2 $BIN_PATH/admetlab_pred.py -i $wd -o $wd -t $threads -sf $suffix
