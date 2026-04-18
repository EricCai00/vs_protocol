#!/bin/bash
PYTHON3=/public/home/caiyi/software/miniconda3/bin/python
CODE_PATH=/public/home/caiyi/eric_github/vs_protocol
DD_CODE_PATH=/public/home/caiyi/eric_github/vs_protocol/dd_code
LIB_PATH=/public/home/caiyi/install/lib64:/public/home/caiyi/install/cuda-11.6/lib64

usage() {
cat <<EOF
Run parallel DeepDocking training jobs for a lot of sets of hyperparameters on GPU.

Usage: distributed_train_dd.sh -d <working_directory> -g <indices_of_gpus> -s <indices_of_jobs> [-p <jobs_per_gpu>]

Example: bash distributed_train_dd.sh -d /public/home/caiyi/data/docking/DeepDocking/projects/plk1_1M/iteration_1 -p 2 -g 3-5 -s 0-5
EOF
}

[ "$1" = "" ] && usage && exit 1;

jobs_per_gpu=1
while getopts "d:g:s:t:p:h" opt; do
    case $opt in
        d) wd=$OPTARG;;
        g) gpu=$OPTARG;;
        s) job=$OPTARG;;
        t) auto_threads=$OPTARG;;
        p) jobs_per_gpu=$OPTARG;;
        h) usage;
           exit 1;;
        ?) echo "Invalid options!"
           exit 1;;
    esac
done


# if [[ $(echo $gpu | grep ",") == "" ]]; then
#     start=$(echo $gpu | awk -F "-" '{print $1}')
#     end=$(echo $gpu | awk -F "-" '{print $2}')
#     [[ $end -lt $start ]] && echo 'Invalid gpu string!' && exit 1
#     gpu_array_single=($(seq $start $end))
# else
#     temp=$(echo $gpu | tr ',' ' ')
#     gpu_array_single=($temp)
# fi 

if [[ $(echo $job | grep "-") != "" ]]; then
    start=$(echo $job | awk -F "-" '{print $1}')
    end=$(echo $job | awk -F "-" '{print $2}')
    [[ $end -lt $start ]] && echo 'Invalid job string!' && exit 1
    job_array=($(seq $start $end))

else
    temp=$(echo $job | tr ',' ' ')
    job_array=($temp)
fi

IFS=$' ' read -r -a gpu_array <<< $($PYTHON3 $CODE_PATH/parse_nvidia-smi.py $auto_threads)
actual_threads=${#gpu_array[@]}

echo TRAINING DL MODEL USING $actual_threads GPUS: ${gpu_array[@]}

for i in $(seq 1 $jobs_per_gpu); do
    gpu_final_array=(${gpu_final_array[@]} ${gpu_array[@]})
done

while [ ! ${#job_array[@]} -eq 0 ]; do
    i=0
    for job_idx in ${job_array[@]:0:${#gpu_final_array[@]}}; do
    sleep 1
    {
        index=${gpu_final_array[$i]}
        node_id=${index%:*}
        gpu_id=${index#*:}
        time1=$(date +%s.%2N)
        ssh gpu$node_id "cd $DD_CODE_PATH; export LD_LIBRARY_PATH=$LIB_PATH; " \
            "CUDA_VISIBLE_DEVICES=$gpu_id bash $wd/simple_job/simple_job_$job_idx.sh"
        time2=$(date +%s.%2N)
        time_delta=$(echo $time2 $time1 | awk '{print($1-$2)}')
        echo job $job_idx: $time_delta $(date +%H:%M:%S.%3N) >> $wd/training_time.txt
    } &
    i=$((i+1))
    done
    job_array=(${job_array[@]:$actual_threads:10000})
wait
done

