import sys
from rdkit import Chem

with open(f'/public/home/caiyi/data/vs_protocol/library/smile_all_{int(sys.argv[1]):02}.txt') as f:
    lines = f.read().splitlines()

fo = open(f'/public/home/caiyi/data/vs_protocol/library/smiles_prepared_{sys.argv[1]}.txt', 'w')
for line in lines:
    try:
        smi, name = line.split()
        mol = Chem.MolFromSmiles(smi)
        fo.write(f'{Chem.MolToSmiles(mol)} {name}\n')
    except:
        pass
fo.close()