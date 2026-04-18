IFS=$' ' read -r -a array <<< $(echo 1 2 3); echo array0: ${array[0]}; echo array1: ${array[1]}
IFS=$' ' read -r -a array <<< $(/public/home/caiyi/software/miniconda3/bin/python /public/home/caiyi/code/vs_integrated/parse_pbsstat.py 90); echo array0: ${array[0]}; echo array1: ${array[1]}
IFS=$'\n' read -r -a array <<< $(/public/home/caiyi/software/miniconda3/bin/python /public/home/caiyi/code/vs_integrated/parse_pbsstat.py 90); echo array0: ${array[0]}; echo array1: ${array[1]}
