#!/public/home/caiyi/software/miniconda3/bin/python

from rdkit import Chem
import numpy as np
import pandas as pd
import math
from tqdm import tqdm
from glob import glob
import argparse
import pathlib

def ads(x, a, b, c, d, e, f, dmax):
  """ ADS function """
  exp1 = 1 + math.exp(-1 * (x - c + d / 2) / e)
  exp2 = 1 + math.exp(-1 * (x - c - d / 2) / f)
  dx = a + b / exp1 * (1 - 1 / exp2)
  return dx / dmax

regression = ['LogS', 'LogD7.4', 'LogP', 'Caco-2', 'PPB', 'VD', 'CL', 'T1/2', 'LD50 of acute toxicity']
classification = ['Pgp-inhibitor', 'Pgp-substrate', 'HIA', 'F (20%)', 'F (30%)', 'BBB', 'CYP1A2-Inhibitor', 'CYP1A2-Substrate', 'CYP2C19-Inhibitor', 'CYP2C19-Substrate', 'CYP2C9-Inhibitor', 'CYP2C9-Substrate', 'CYP2D6-Inhibitor', 'CYP2D6-Substrate', 'CYP3A4-Inhibitor', 'CYP3A4-Substrate', 'hERG', 'H-HT', 'Ames', 'SkinSen']
harmful = ['Pgp-inhibitor', 'Pgp-substrate', 'BBB', 'CYP1A2-Inhibitor', 'CYP2C19-Inhibitor', 'CYP2C9-Inhibitor', 'CYP2D6-Inhibitor', 'CYP3A4-Inhibitor', 'hERG', 'H-HT', 'Ames', 'SkinSen']

threshold = {
    'LogS': (-4, 0.5),
    'LogD7.4': (1, 5),
    'LogP': (0, 3),
    'Caco-2': (-5.15, np.inf), 
    'PPB': (-np.inf, 90),
    'VD': (0.04, 20),
    'CL': (5, np.inf),
    'T1/2': (3, np.inf),
    'LD50 of acute toxicity': (np.log10(500), np.inf)
}

w2 = {
# Q^2
'LogS': 0.967,   # 0.860 in paper
'LogD7.4': 0.877,
'Caco-2': 0.845,
'PPB': 0.691,
# 3-fold rate (Test)
'VD': 0.904,   # 0.634 in paper
'CL': 0.897,
'T1/2': 0.824,
'LD50 of acute toxicity': 0.997,
# Accuracy
'HIA': 0.773,
'F (20%)': 0.671,
'F (30%)': 0.667,
'BBB': 0.962,
'Pgp-inhibitor': 0.838,
'Pgp-substrate': 0.84,
'CYP1A2-Inhibitor': 0.867,
'CYP1A2-Substrate': 0.702,
'CYP3A4-Inhibitor': 0.829,
'CYP3A4-Substrate': 0.749,
'CYP2C19-Inhibitor': 0.819,
'CYP2C19-Substrate': 0.769,
'CYP2C9-Inhibitor': 0.83,
'CYP2C9-Substrate': 0.734,
'CYP2D6-Inhibitor': 0.795,
'CYP2D6-Substrate': 0.76,
'hERG': 0.848,
'H-HT': 0.681,
'Ames': 0.834,
'SkinSen': 0.731
}
w2['LogP'] = np.mean(list(w2.values()))

w3 = {
# Physical
'LogS': 1,  # default
'LogD7.4': 1,  # default
'LogP': 1,  # default
# Absorption
'Caco-2': 0.8,  # 0.8
'Pgp-inhibitor': 0.8,  # 0.8
'Pgp-substrate': 0.8,  # 0.8
'HIA': 1,   # 1
'F (20%)': 0.5,  # default
'F (30%)': 0.5,  # default
# Distribution
'PPB': 0.8,  # default
'VD': 0.8,  # default
'BBB': 0.8,  # default
# Metabolism
'CYP1A2-Inhibitor': 0.5, # 0.5
'CYP1A2-Substrate': 0.5,  # inferred
'CYP3A4-Inhibitor': 0.8, # 0.8
'CYP3A4-Substrate': 0.8, # 0.8
'CYP2C19-Inhibitor': 0.5, # 0.5
'CYP2C19-Substrate': 0.5,  # inferred
'CYP2C9-Inhibitor': 0.5, # 0.5
'CYP2C9-Substrate': 0.5, # 0.5
'CYP2D6-Inhibitor': 0.5, # 0.5
'CYP2D6-Substrate': 0.5, # 0.5
# Excretion
'CL': 1,  # default
'T1/2': 1,  # default
# Toxicity
'LD50 of acute toxicity': 1, # 1
'hERG': 1, # 1
'H-HT': 1,  # default
'Ames': 1, # 1
'SkinSen': 1  # default
}


def admetlab_score(input_, output, name_field, keep_nan):
        
    code_dir = pathlib.Path(__file__).parent.resolve()
    with open(f'{code_dir}/admet_score_data/approved_oral_revised.smi', encoding='gbk') as f:
        lines = f.read().splitlines()

    drug_list = []
    for line in lines:
        smi, name = line.split()
        drug_list.append(name)
    db_name_array = np.array(drug_list)

    df_db = pd.read_csv(f'{code_dir}/admet_score_data/results_drugbank.csv', index_col=0)
    df_db['LD50 of acute toxicity'] = np.log10(df_db['LD50 of acute toxicity'])
    df_train = df_db.loc[db_name_array]

    w1 = {}
    for key in regression:
        p = sum(np.logical_and(df_train[key] > threshold[key][0], df_train[key] < threshold[key][1])) / len(df_train)
        if p == 0:
            p += 1e-4
        w1[key] = (0.75 * p) + 0.25

    for key in classification:
        p = sum(df_train[key] > 0.5) / len(df_train)
        if key in harmful:
            p = 1 - p
        w1[key] = (0.75 * p) + 0.25

    w = {}
    for key in w1:
        w[key] = w1[key] * w2[key] * w3[key]
    w_sum = 0
    for key in regression + classification:
        w_sum += w[key]

    path = f'{code_dir}/admet_score_data/ads_fit'
    ads_param = {}
    for key in regression:
        fn = key.replace('/', '_')
        fn = fn.replace(' ', '_')
        with open(f'{path}/{fn}.txt') as f:
            lines = f.read().splitlines()
        param_names = 'abcdef'
        param_list = []
        for i, line in enumerate(lines):
            if len(line) > 2 and line[0] == ' ' and line[1] in param_names:
                param_list.append(float(line.split()[1]))
            if line.startswith('Function min'):
                param_list.append(float(lines[i+1].split()[2]))

        ads_param[key] = param_list

    file_list = glob(input_)

    df_list = []
    for file in file_list:
        df_list.append(pd.read_csv(file))
    df = pd.concat(df_list)
    df.index = [i for i in range(len(df))]

    if name_field == 'index':
        get_name = lambda example, i: i
    else:
        get_name = lambda example, i: example[name_field]

    fo = open(output, 'w')
    fo.write('name,score\n')
    for i in tqdm(df.index):
        example = df.loc[i]
        name = get_name(example, i)
        log_score = 0
        for key in regression:
            if key in w:
                a, b, c, d, e, f, dmax = ads_param[key]
                dx = ads(example[key], a, b, c, d, e, f, dmax)
                log_score += w[key] * np.log(dx)
                # print(key, dx)

        for key in classification:   
            if key in w: 
                if key in harmful:
                    dx = 1 - example[key]
                else:
                    dx = example[key]
                if dx == 0:
                    dx += 1e-5
                log_score += w[key] * np.log(dx)

        score = np.exp(log_score / w_sum)
        if not np.isnan(score) or keep_nan:
            fo.write(f'{name},{score}\n')
    fo.close()

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True)
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('-n', '--name_field', required=True)
    parser.add_argument('-k', '--keep_nan', action='store_true')
    args = parser.parse_args()

    admetlab_score(args.input, args.output, args.name_field, args.keep_nan)
