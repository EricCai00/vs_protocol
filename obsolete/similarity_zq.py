#conda activate my-rdkit-env
#python similarity.py
from rdkit import Chem
from rdkit.Chem 
from rdkit import DataStructs
import tqdm

with open('/public2022/zhangqian/compounds_data/lipinski_total/smi/Mcule_1.smi') as f:
    lines = f.read().splitlines()[1:]
    
query = ['CC1=NC2=C(C=CC=C2)C(C(NNC(C3=CC(S(=O)(N4CCOCC4)=O)=CC=C3)=O)=O)=C1']
query = [Chem.MolFromSmiles(q) for q in query]

from multiprocessing import Pool
import math

num_threads = 50

def cal_simi(line_split):
    simi = [[] for i in range(len(query))]
    #f_o = open('similarity.txt', 'w')
    for i, q in enumerate(query):
        #f_o = open(f'similarity_{i}.txt', 'w')
        for smi in tqdm.tqdm(line_split):
            try:
                mol = Chem.MolFromSmiles(smi)
                fp = AllChem.GetMorganFingerprint(mol, 3)
                fp_q = AllChem.GetMorganFingerprint(q, 3)
                s = DataStructs.TanimotoSimilarity(fp, fp_q)
                simi[i].append((smi, s))
                #f_o.write(f'{smi} {s}\n')
            #f_o.close()
            except:
                continue
    return simi

split_len = math.ceil(len(lines) / num_threads)
line_splits = [lines[i * split_len: (i+1) * split_len] for i in range(num_threads)]

with Pool(num_threads) as pool:
    out_list = pool.map(cal_simi, line_splits)

final_list = [[] for i in range(len(query))]
for i in range(len(out_list)):
    for j in range(len(out_list[i])):
        final_list[j].extend(out_list[i][j])

for i in [0,1,2]:
    sorted_list = sorted(final_list[i], key=lambda x: x[1], reverse=True)
    with open(f'/public2022/zhangqian/similarityscreening/PLK1_similarity/Mcule_{i}.txt', 'w') as f:
        for item in sorted_list:
            f.write(item[0] + '\t' + str(item[1]) + '\n')
