#!/bin/bash

UNIDOCK=/public/home/caiyi/software/miniconda3/envs/unidock/bin/unidock
CODE_PATH=/public/home/caiyi/eric_github/vs_protocol
PYTHON3=/public/home/caiyi/software/miniconda3/bin/python

usage() {
cat <<EOF
Usage: distributed_unidock.sh -c <config_file> -r <receptor_pdbqt> -d <working_directory> -n <file_name_prefix> -t <threads> -m <search_mode:fast/balance> [-l <list> -x <suffix>]

Example: bash distributed_unidock.sh -c /public/home/caiyi/data/docking/unidock_protocol/vs/plk1_uni/config_2rku_revised.txt \
-r /public/home/caiyi/data/docking/unidock_protocol/vs/plk1_uni/2rku.pdbqt \
-d /public/home/caiyi/data/docking/unidock_protocol/vs/plk1_uni/iteration_1 -n train -t 8 -m fast \
-l train_not_docked.txt 
EOF
}

[ "$1" = "" ] && usage && exit 1;

# while getopts "c:r:d:n:t:g:s:hx::" opt; do
while getopts "c:r:d:n:t:l:m:hx::" opt; do
    case $opt in
        c) config=$OPTARG;;
        r) receptor=$OPTARG;;
        d) wd=$OPTARG;;
        n) name=$OPTARG;;
        # g) gpu=$OPTARG;;
        # s) split=$OPTARG;;
        t) auto_threads=$OPTARG;;
	    x) suffix=$OPTARG;;
	    l) list=$OPTARG;;
        m) search_mode=$OPTARG;;
        h) usage;
           exit 1;;
        ?) echo "Invalid options!"
           exit 1;;
    esac
done

PWD=$(pwd)

config=$(readlink -f $config)
receptor=$(readlink -f $receptor)
wd=$(readlink -f $wd)

if [ ! -d $wd/${name}_docked$suffix ]; then
    mkdir $wd/${name}_docked$suffix
# elif [ "$(ls -A $wd/${name}_docked)" ]; then
#     echo "Directory $wd/${name}_docked is not empty!"
#     exit 1
fi

# IFS=$'\n' read -r -a gpu_array <<< $($PYTHON3 $CODE_PATH/parse_nvidia-smi.py $auto_threads)
mapfile -t gpu_array < <($PYTHON3 $CODE_PATH/parse_nvidia_smi.py $auto_threads)
actual_threads=${#gpu_array[@]}

if [ ! -z $list ]; then
    echo bash $CODE_PATH/split_pdbqt_list.sh -d $wd -n $name -s $actual_threads -l $list
    bash $CODE_PATH/split_pdbqt_list.sh -d $wd -n $name -s $actual_threads -l $list
else
    echo bash $CODE_PATH/split_pdbqt_list.sh -d $wd -n $name -s $actual_threads
    bash $CODE_PATH/split_pdbqt_list.sh -d $wd -n $name -s $actual_threads
fi

echo PERFORMING UNIDOCK USING $actual_threads GPUS: ${gpu_array[@]}

for i in `seq 0 $((actual_threads-1))`; do
    index=${gpu_array[$i]}
    node_id=${index%:*}
    gpu_id=${index#*:}
    split_file=$wd/${name}_list_split/${name}_list_split_$(printf "%02d" $i).txt
    sleep 1
    # upper limit for grid volume for gpu docking is about 51064.8
    echo ssh gpu$node_id "cd $wd/${name}_pdbqt; CUDA_VISIBLE_DEVICES=$gpu_id $UNIDOCK --receptor $receptor --ligand_index $split_file \
        --config $config --dir $wd/${name}_docked$suffix/ --verbosity 0 --search_mode $search_mode"  &
    ssh gpu$node_id "cd $wd/${name}_pdbqt; CUDA_VISIBLE_DEVICES=$gpu_id $UNIDOCK --receptor $receptor --ligand_index $split_file \
        --config $config --dir $wd/${name}_docked$suffix/ --verbosity 0 --search_mode $search_mode"  &
    
    # ssh gpu$node_id "cd $wd/${name}_pdbqt; CUDA_VISIBLE_DEVICES=$gpu_id $UNIDOCK --receptor $receptor --ligand_index $split_file \
    #     --config $config --dir $wd/${name}_docked$suffix/ --verbosity 0 --search_mode $search_mode"  &
done

wait