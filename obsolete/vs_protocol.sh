PYTHON3=/public/home/caiyi/software/miniconda3/bin/python
PYTHON2=/public/home/caiyi/software/miniconda3/envs/python2/bin/python2
CODE_PATH=/public/home/caiyi/eric_github/vs_protocol
PREPARE_RECEPTOR4=/public/home/caiyi/software/miniconda3/envs/python2/bin/prepare_receptor4.py
# LIBRARY_PATH=/public/home/caiyi/data/vs_protocol/targetmol_fp

usage() {
cat <<EOF
Usage: vs_protocol.sh -d <working_directory> -p <project_name> -r <receptor_pdb> -c <protocol_config_file>
            

Example: bash vs_protocol.sh -d ~/data/vs_protocol -p tryout\
 -r ~/data/vs_protocol/tryout/receptor/2rku.pdb\
 -c ~/data/vs_protocol/tryout/protocol_config.yaml
EOF
}

[ "$1" = "" ] && usage && exit 1;

# OPTS=$(getopt -o d:p:r:l:h --long wd:,project:,receptor:,library:,help \
#     -n 'vs_protocol.sh' -- "$@")

if [ $? != 0 ] ; then echo "Failed parsing options." >&2 ; exit 1 ; fi

# eval set -- "$OPTS"

tot_iters=11
# sampling_size=1000
start_iter=1
start_step="sample"
start_set="train"
perform_substruct=0
perform_simi=0
simi_threshold=0.3
substruct_list=/public/home/caiyi/data/vs_protocol/substructures.txt

while true; do
  case "$1" in
    -d | --wd ) wd="$2"; shift 2;;
    -p | --project ) project_name="$2"; shift 2;;
    -r | --receptor ) receptor_path="$2"; shift 2;;
    -l | --library ) library="$2"; shift 2;;
    -sl | --substruct_list ) substruct_list="$2"; shift 2;;
    -sq | --simi_query ) simi_query="$2"; shift 2;;
    -st | --simi_threshold ) simi_threshold="$2"; shift 2;;
    -psub | --perform_substruct ) perform_substruct="$2"; shift 2;;
    -psim | --perform_simi ) perform_simi="$2"; shift 2;;
    -h | --help ) usage; exit 0;;
    -- ) shift; break;;
    * ) break;;
  esac
done

# Upload and process the PDB structure
echo "--------------------Process Target PDB--------------------"

if [ ! -d $wd/$project_name/receptor ]; then
    mkdir $wd/$project_name/receptor
fi

echo $PYTHON3 $CODE_PATH/extract_ligand.py -i $receptor_path -o $wd/$project_name/receptor -pf $project_name
$PYTHON3 $CODE_PATH/extract_ligand.py -i $receptor_path -o $wd/$project_name/receptor -pf $project_name

echo $PYTHON2 $PREPARE_RECEPTOR4 -r $wd/$project_name/receptor/${project_name}_clean.pdb -o $wd/$project_name/receptor/${project_name}_clean.pdbqt -A hydrogens
$PYTHON2 $PREPARE_RECEPTOR4 -r $wd/$project_name/receptor/${project_name}_clean.pdb -o $wd/$project_name/receptor/${project_name}_clean.pdbqt -A hydrogens

# Module 3 - Known inhibtor
echo "--------------------MODULE 3: Known Inhibitors--------------------"

if [ ! -d $wd/$project_name/module_3 ]; then
    mkdir $wd/$project_name/module_3
fi

# a) Substructure Similarity Filtering
if [ $perform_substruct -eq 1 ]; then
  simi_input=$wd/$project_name/module_3/matched_at_least_one.smi
  filtered_library=$wd/$project_name/module_3/matched_at_least_one.smi

  echo $PYTHON3 $CODE_PATH/module_3/substructure.py -i $library -o $wd/$project_name/module_3 -l $substruct_list
  $PYTHON3 $CODE_PATH/module_3/substructure.py -i $library -o $wd/$project_name/module_3 -l $substruct_list
else
  simi_input=$library
  filtered_library=$library
fi

# b) Fingerprints Similarity Filtering
if [ $perform_simi -eq 1 ]; then
  filtered_library=$wd/$project_name/module_3/filtered_library.smi

  echo $PYTHON3 $CODE_PATH/module_3/calc_simi.py -i $simi_input -o $wd/$project_name/module_3/similarity.csv\
   -q $simi_query
  $PYTHON3 $CODE_PATH/module_3/calc_simi.py -i $simi_input -o $wd/$project_name/module_3/similarity.csv\
   -q $simi_query

  echo $PYTHON3 $CODE_PATH/filter_simi.py -i $simi_input -s $wd/$project_name/module_3/similarity.csv\
   -o $wd/$project_name/module_3/filtered_library.smi -t $simi_threshold
  $PYTHON3 $CODE_PATH/filter_simi.py -i $simi_input -s $wd/$project_name/module_3/similarity.csv\
   -o $wd/$project_name/module_3/filtered_library.smi -t $simi_threshold
fi

# Module 4 - Docking
echo "--------------------MODULE 4: Docking--------------------"

# a1) Deep Docking

# a2) Plain Docking

# b) Hydrogen bond filtering

# Module 4a - ADMET / Physicochemical

# Module 5 - Clustering
echo "--------------------MODULE 5: Clustering--------------------"


# Module 6 - Pre-MD
echo "--------------------MODULE 6: Pre-MD--------------------"

# Module 7 - Weighted
echo "--------------------MODULE 7: Weighted--------------------"

# Module 7 - Weighted
echo "--------------------MODULE 7: Weighted--------------------"