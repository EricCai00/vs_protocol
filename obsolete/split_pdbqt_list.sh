#!/bin/bash

usage() {
cat <<EOF
Usage: split_pdbqt_list.sh -d <working_directory> -n <file_name_prefix> -s <number_of_splits> [-l <list_path>]

Example: split_pdbqt_list.sh -d /public/home/caiyi/data/docking/DeepDocking/projects/plk1_1M/iteration_1 -l /public/home/caiyi/data/docking/DeepDocking/projects/plk1_1M/iteration_1/train_not_docked_2.txt -n train -s 3
EOF
}

[ "$1" = "" ] && usage && exit 1;

while getopts "d:n:s:l:hp" opt; do
    case $opt in
        d) wd=$OPTARG;;
        n) name=$OPTARG;;
        s) n_splits=$OPTARG;;
        l) list=$OPTARG;;
        p) include_path=$OPTARG;;
        h) usage;
           exit 1;;
        ?) echo "Wrong options!"
           exit 1;;
    esac
done

PWD=$(pwd)

if [ -z $list ]; then
    list=$wd/${name}_list.txt
    ls $wd/${name}_pdbqt > $list
fi

len=$(wc -l $list | awk '{print $1}')
n1=$(echo $len $n_splits | awk '{printf("%.3f\n", $1/$2)}')
split_len=$(awk -v a=$n1 'BEGIN{print(int(a)==(a))?int(a):int(a)+1}')

if [ ! -d $wd/${name}_list_split ]; then
    mkdir $wd/${name}_list_split
elif [ "$(ls -A $wd/${name}_list_split)" ]; then
    i=1
    while [ -d $wd/${name}_list_split_$i ]; do
        i=$((i+1))
    done
    mv $wd/${name}_list_split $wd/${name}_list_split_$i
    mkdir $wd/${name}_list_split
fi

split -d -l $split_len $list $wd/${name}_list_split/${name}_list_split_ --additional-suffix=.txt
