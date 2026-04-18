PYTHON=/public/home/caiyi/software/miniconda3/bin/python
WEIGHTS_DIR=/public/home/caiyi/eric_github/vs_protocol/weights/druglikeness
CODE_DIR=/public/home/caiyi/eric_github/vs_protocol/module_3/druglikeness
WD=$2
echo $PYTHON $CODE_DIR/predict.py -i $1 -m $WEIGHTS_DIR/generaldl -o $WD/mol_pred.csv
CUDA_VISIBLE_DEVICES=0 $PYTHON $CODE_DIR/predict.py -i $1 -m $WEIGHTS_DIR/generaldl -o $WD/mol_pred_gen.csv -g 0&
CUDA_VISIBLE_DEVICES=1 $PYTHON $CODE_DIR/predict.py -i $1 -m $WEIGHTS_DIR/specdl-ftt -o $WD/mol_pred_spec-ftt.csv -g 1&
CUDA_VISIBLE_DEVICES=1 $PYTHON $CODE_DIR/predict.py -i $1 -m $WEIGHTS_DIR/specdl-zinc -o $WD/mol_pred_spec-zinc.csv -g 1&
CUDA_VISIBLE_DEVICES=2 $PYTHON $CODE_DIR/predict.py -i $1 -m $WEIGHTS_DIR/specdl-cm -o $WD/mol_pred_spec-cm.csv -g 2&
CUDA_VISIBLE_DEVICES=2 $PYTHON $CODE_DIR/predict.py -i $1 -m $WEIGHTS_DIR/specdl-cp -o $WD/mol_pred_spec-cp.csv -g 2&
wait