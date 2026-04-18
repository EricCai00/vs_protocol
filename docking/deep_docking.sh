#!/bin/bash
PYTHON3=/public/home/caiyi/software/miniconda3/bin/python
DD_DATA_PATH=/public/home/caiyi/data/docking/DeepDocking
CODE_PATH=/public/home/caiyi/eric_github/vs_protocol
DD_CODE_PATH=/public/home/caiyi/eric_github/vs_protocol/dd_code
LIBRARY_PATH=/public/home/caiyi/data/docking/DeepDocking/library_prepared_fp
BASH=/usr/bin/bash
# LIBRARY_PATH=/public/home/caiyi/data/docking/unidock_protocol/small_lib_fp
STORAGE_NODE=node3
PREPARE_THREADS=90
SAMPLE_THREADS=60
EXTRACT_THREADS=15
GPU_THREADS=4

usage() {
cat <<EOF
Usage: deep_docking.sh -d <working_directory> -p <project_name> -r <receptor_pdbqt> -c <config_path>\
 -n <num_of_iterations> -N <sampling_size> [-i <resume_from_iter> -s <resume_from_step> -e <resume_from_set>]
            

Example: bash deep_docking.sh -d ~/data/docking/unidock_protocol/vs -p tryout -r ~/data/docking/unidock_protocol/vs/tryout/2rku.pdbqt\
 -c ~/data/docking/unidock_protocol/vs/tryout/config_2rku_revised.txt -n 11 -N 1000 -i 1 -s predict 
EOF
}

[ "$1" = "" ] && usage && exit 1;

OPTS=$(getopt -o d:p:r:c:n:N:i:s:e:h --long wd:,project:,receptor:,config:,tot_iters:,sampling:,start_iter:,start_step:,help \
    -n 'deep_docking.sh' -- "$@")

if [ $? != 0 ] ; then echo "Failed parsing options." >&2 ; exit 1 ; fi

eval set -- "$OPTS"

tot_iters=11
# sampling_size=1000
start_iter=1
start_step="sample"
start_set="train"


while true; do
  case "$1" in
    -d | --wd ) wd="$2"; shift 2;;
    -p | --project ) project_name="$2"; shift 2;;
    -r | --receptor ) receptor_path="$2"; shift 2;;
    -c | --config ) config_path="$2"; shift 2;;
    -n | --tot_iters ) tot_iters="$2"; shift 2;;
    -N | --sampling ) sampling_size="$2"; shift 2;;
    -i | --start_iter ) start_iter="$2"; shift 2;;
    -s | --start_step ) start_step="$2"; shift 2;;
    -e | --start_set ) start_set="$2"; shift 2;;
    -h | --help ) usage; exit 0;;
    -- ) shift; break;;
    * ) break;;
  esac
done

echo "working_directory: $wd"
echo "project_name: $project_name"
echo "receptor_path: $receptor_path"
echo "config_path: $config_path"
echo "total_iterations: $tot_iters"
echo "sampling_size: $sampling_size"
echo "start_iteration: $start_iter"
echo "start_step: $start_step"

if [ -z "$wd" ] || [ -z "$project_name" ] || [ -z "$receptor_path" ] || [ -z "$config_path" ]; then
    echo "Error: Missing required arguments!"
    usage
    exit 1
fi

declare -A step_dict=([sample]=1 [prepare]=2 [dock]=3 [extract]=4 [train]=5 [evaluate]=6 [predict]=7)
start_step_code=${step_dict[$start_step]}

for n in `seq $start_iter $tot_iters`; do
    echo "--------------------ITERATION $n: SAMPLING--------------------"
    if [ $n -eq $start_iter ] && [ $start_step_code -gt 1 ]; then
        echo "Skipping the step of sampling."
    else
        if [ $n -eq 1 ]; then
            data_directory=$LIBRARY_PATH
            tot_sampling=$((3*$sampling_size)) 
        else
            data_directory=$wd/$project_name/iteration_$((n-1))/morgan_1024_predictions
            tot_sampling=$sampling_size
        fi

        echo $PYTHON3 $DD_CODE_PATH/molecular_file_count_updated.py --project_name $project_name \
                --n_iteration $n --data_directory $data_directory \
                --tot_process $SAMPLE_THREADS --tot_sampling $tot_sampling
        $PYTHON3 $DD_CODE_PATH/molecular_file_count_updated.py --project_name $project_name \
                --n_iteration $n --data_directory $data_directory \
                --tot_process $SAMPLE_THREADS --tot_sampling $tot_sampling

        echo $PYTHON3 $DD_CODE_PATH/sampling.py --project_name $project_name --file_path $wd \
            --n_iteration $n --data_directory $data_directory \
            --tot_process $SAMPLE_THREADS --train_size $sampling_size --val_size $sampling_size
        $PYTHON3 $DD_CODE_PATH/sampling.py --project_name $project_name --file_path $wd \
            --n_iteration $n --data_directory $data_directory \
            --tot_process $SAMPLE_THREADS --train_size $sampling_size --val_size $sampling_size

        echo $PYTHON3 $DD_CODE_PATH/sanity_check.py --project_name $project_name --file_path $wd --n_iteration $n
        $PYTHON3 $DD_CODE_PATH/sanity_check.py --project_name $project_name --file_path $wd --n_iteration $n

        echo $PYTHON3 $DD_CODE_PATH/extracting_morgan.py --project_name $project_name --file_path $wd \
            --n_iteration $n --morgan_directory $LIBRARY_PATH --tot_process $SAMPLE_THREADS
        $PYTHON3 $DD_CODE_PATH/extracting_morgan.py --project_name $project_name --file_path $wd \
            --n_iteration $n --morgan_directory $LIBRARY_PATH --tot_process $SAMPLE_THREADS

        echo $PYTHON3 $DD_CODE_PATH/extracting_smiles.py --project_name $project_name --file_path $wd \
            --n_iteration $n --smile_directory ${LIBRARY_PATH%_*} --tot_process $SAMPLE_THREADS
        $PYTHON3 $DD_CODE_PATH/extracting_smiles.py --project_name $project_name --file_path $wd \
            --n_iteration $n --smile_directory ${LIBRARY_PATH%_*} --tot_process $SAMPLE_THREADS
        # exit 1
    fi

    echo "--------------------ITERATION $n: PREPARING LIGANDS--------------------"
    if [ $n -eq $start_iter ] && [ $start_step_code -gt 2 ]; then
        echo "Skipping the step of preparing ligands."
    else
        names=("train" "valid" "test")
        if [ $n -eq $start_iter ] && [ $start_step_code -eq 2 ]; then
            case $start_set in
                "train" ) names=("train" "valid" "test");;
                "valid" ) names=("valid" "test");;
                "test" ) names=("test");;
                * ) echo "Unknown set"; exit 1;;
            esac
        fi
        
        for name in "${names[@]}"; do
            echo PREPARING LIGANDS FOR $name: $BASH $CODE_PATH/distributed_prepare_ligand.sh \
                -i $wd/$project_name/iteration_$n/smile/${name}_smiles_final_updated.smi -o $wd/$project_name/iteration_$n/${name}_pdbqt \
                -t $PREPARE_THREADS -f
            $BASH $CODE_PATH/distributed_prepare_ligand.sh -i $wd/$project_name/iteration_$n/smile/${name}_smiles_final_updated.smi \
                -o $wd/$project_name/iteration_$n/${name}_pdbqt -t $PREPARE_THREADS -f
            echo PREPARED NUM FOR $name: $(ssh $STORAGE_NODE "ls $wd/$project_name/iteration_$n/${name}_pdbqt | wc -l")
        done
        # exit 1
    fi
    wait

    echo "--------------------ITERATION $n: DOCKING--------------------"
    if [ $n -eq $start_iter ] && [ $start_step_code -gt 3 ]; then
        echo "Skipping the step of docking."
    else        
        names=("train" "valid" "test")
        if [ $n -eq $start_iter ] && [ $start_step_code -eq 3 ]; then
            case $start_set in
                "train" ) names=("train" "valid" "test");;
                "valid" ) names=("valid" "test");;
                "test" ) names=("test");;
                * ) echo "Unknown set"; exit 1;;
            esac
        fi

        for name in "${names[@]}"; do
            echo DOCKING FOR $name: $BASH $CODE_PATH/distributed_unidock.sh -c $config_path -r $receptor_path \
                -d $wd/$project_name/iteration_$n/ -n $name -t $GPU_THREADS -m fast
            $BASH $CODE_PATH/distributed_unidock.sh -c $config_path -r $receptor_path \
                -d $wd/$project_name/iteration_$n/ -n $name -t $GPU_THREADS -m fast
            echo DOCKED NUM FOR $name: $(ssh $STORAGE_NODE "ls $wd/$project_name/iteration_$n/${name}_docked | wc -l")
        done
        # exit 1
    fi

    echo "--------------------ITERATION $n: EXTRACTING SCORES--------------------"
    if [ $n -eq $start_iter ] && [ $start_step_code -gt 4 ]; then
        echo "Skipping the step of extracting scores."
    else
        names=("train" "valid" "test")
        for name in "${names[@]}"; do
            node=$($PYTHON3 $CODE_PATH/parse_pbsstat.py best)
            echo EXTRACTING SCORE FOR $name: ssh $node $PYTHON3 $CODE_PATH/extract_vina_score.py --name $name \
                --docked_dir $wd/$project_name/iteration_$n/${name}_docked --output_dir $wd/$project_name/iteration_$n/ --threads $EXTRACT_THREADS
            ssh $node $PYTHON3 $CODE_PATH/extract_vina_score.py --name $name --docked_dir $wd/$project_name/iteration_$n/${name}_docked \
                --output_dir $wd/$project_name/iteration_$n/ --threads $EXTRACT_THREADS
        done
        # exit 1
    fi

    echo "--------------------ITERATION $n: TRAINING MODELS--------------------"
    if [ $n -eq $start_iter ] && [ $start_step_code -gt 5 ]; then
        echo "Skipping the step of training models."
    else
        is_last=False
        if [ $n -eq $tot_iters ]; then is_last=True; fi

        cd $DD_CODE_PATH
        echo RUNNING $DD_CODE_PATH/simple_job_models_manual.py
        # Do not put '/' on the end of `file_path`
        $PYTHON3 $DD_CODE_PATH/simple_job_models_manual.py --iteration_no $n --morgan_directory $LIBRARY_PATH --file_path $wd/$project_name \
            --number_of_hyp 24 --total_iterations $tot_iters --is_last $is_last --number_mol $sampling_size \
            --percent_first_mols 1 --percent_last_mols 0.01 --recall 0.90

        echo RUNNING $CODE_PATH/distributed_train_dd.sh

        $BASH $CODE_PATH/distributed_train_dd.sh -d $wd/$project_name/iteration_$n -t $GPU_THREADS -s 1-24
        # exit 1
    fi

    echo "--------------------ITERATION $n: EVALUATING MODELS--------------------"
    if [ $n -eq $start_iter ] && [ $start_step_code -gt 6 ]; then
        echo "Skipping the step of evaluating models."
    else
        echo RUNNING $DD_CODE_PATH/hyperparameter_result_evaluation.py
        $PYTHON3 $DD_CODE_PATH/hyperparameter_result_evaluation.py --n_iteration $n --data_path $wd/$project_name \
            --morgan_directory $LIBRARY_PATH --number_mol $sampling_size --recall 0.90
        # exit 1
    fi

    echo "--------------------ITERATION $n: PREDICTING LIBRARY--------------------"
    if [ $n -eq $start_iter ] && [ $start_step_code -gt 7 ]; then
        echo "Skipping the step of predicting library."
    else
        cd $DD_CODE_PATH
        $PYTHON3 $DD_CODE_PATH/simple_job_predictions_manual.py --project_name $project_name \
            --file_path $wd --n_iteration $n --morgan_directory $LIBRARY_PATH

        $BASH $CODE_PATH/distributed_infer_dd.sh -d $wd/$project_name/iteration_$n -t $GPU_THREADS -s 1-101 -p 3
        # exit 1
    fi

done