#!/public/home/caiyi/software/miniconda3/envs/python2/bin/python

import math
import argparse
import json
from glob import glob
from multiprocessing import Pool
import os

import h5py
import numpy as np
import pandas as pd
from sklearn.externals import joblib

MODULE_PATH = os.path.abspath(os.path.dirname(__file__))
WEIGHTS_PATH = os.path.dirname(MODULE_PATH) + '/weights/admetlab/'
path  = '/public/home/caiyi/github/admet/ADMETlab/'
fp_list = ['MACCS', 'ECFP2_2048', 'ECFP4_1024', 'ECFP4_2048', 'ECFP6_2048']

usage = ('admetlab_pred.py --input_dir <dir_path> --output_dir <dir_path> [--threads <int> --suffix <str>]\n\n'
'Example: admetlab_pred.py -i /public/home/caiyi/data/admet/admetlab/ -o /public/home/caiyi/data/admet/admetlab/ -t 20 -sf 00')

parser = argparse.ArgumentParser(usage=usage)
parser.add_argument('-i', '--input_dir', required=True)
parser.add_argument('-o', '--output_dir', required=True)
parser.add_argument('-sf', '--suffix', type=str)
parser.add_argument('-t', '--threads', default=1, type=int)
parser.add_argument('-c', '--chunk_size', default=100000, type=int)
args = parser.parse_args()


def lipinski(d):
    res = np.array([d['MW'] <= 500, d['LogP'] <= 5, d['naccr'] <= 10, d['ndonr'] <= 5])
    return res.mean(0)

def ghose(d):
    res = np.array([np.logical_and(d['LogP'] > 0.4, d['LogP'] < 5.6),
                    np.logical_and(d['MW'] > 160, d['MW'] < 480),
                    np.logical_and(d['MR'] > 40, d['MR'] < 130),
                    np.logical_and(d['nta'] > 20, d['nta'] < 70)])
    return res.mean(0)

def oprea(d):
    res = np.array([d['nring'] >= 3, d['nrigidbond'] >= 18, d['nRotbond'] >= 6])
    return res.mean(0)

def veber(d):
    res = np.array([d['nRotbond'] <= 10,
                    np.logical_or(d['TPSA'] <= 140, d['naccr'] + d['ndonr'] <= 12)])
    return res.mean(0)

def varma(d, r):
    res = np.array([d['MW'] <= 500,
                    d['TPSA'] <= 125,
                    np.logical_and(r['LogD7.4'] > 2, r['LogD7.4'] < 5),
                    d['naccr'] + d['ndonr'] <= 9,
                    d['nRotbond'] <= 12])
    return res.mean(0)


df_meta = pd.read_csv(MODULE_PATH + '/admetlab_models.csv', index_col=0)
df_meta = df_meta[df_meta['Model path'].notnull()]
des_path = '/descriptors_' + args.suffix + '.csv' if args.suffix else '/descriptors.csv'
df_des = pd.read_csv(args.input_dir + des_path, index_col=0)
with open(MODULE_PATH + '/admetlab_labels.json', 'r') as f:
    label_dict = json.load(f)

fp_dict = {}
# smiles_dict = {}
name_dict = {}
for fp_name in fp_list:
    fp_file_name = '/' + fp_name + '_' + args.suffix + '.h5' if args.suffix else '/' + fp_name + '.h5'
    f = h5py.File(args.input_dir + fp_file_name, 'r')
    fp_dict[fp_name] = np.array(f['array'])
    # smiles_dict[fp_name] = list(np.array(f['smiles']))
    name_dict[fp_name] = list(np.array(f['name']))
    f.close()

df_des_name = list(map(str, df_des.index))
for fp_name, name_list in name_dict.items():
    # Caution: do not contain duplicate smiles when generating descriptors/fingerprints
    print(name_list[:5], df_des_name[:5])
    print(len(name_list), len(df_des_name))
    assert name_list == df_des_name

def predict(index):
    res = {}
    start, end = index
    prop_list = df_meta.index
    # prop_list = list(df_meta[df_meta['Descriptor'] == '2D'].index)
    for prop in prop_list:
        task_type = df_meta.loc[prop, 'Type']
        model_path = df_meta.loc[prop, 'Model path']
        model_type = df_meta.loc[prop, 'Method']
        des_name = df_meta.loc[prop, 'Descriptor']
        print(prop, model_type, des_name)

        if des_name == '2D':
            des_array = np.array(df_des[label_dict[prop]][start:end])
            inf_index = np.where(np.sum(np.isfinite(des_array), 1) != des_array.shape[1])[0]
            des_array[inf_index] = 0
        else:
            des_array = fp_dict[des_name][start:end]

        if task_type == 'Regression':
            cf = joblib.load(WEIGHTS_PATH + '/' + model_path)
            cf.verbose = 1
            res[prop] = cf.predict(des_array)
            if des_name == '2D':
                res[prop][inf_index] = np.nan
        elif task_type == 'Classification':
            model_paths = glob(WEIGHTS_PATH + '/' + model_path)
            cf_list = [joblib.load(p) for p in model_paths]
            for cf in cf_list:
                cf.verbose = 1
            res_list = [cf.predict_proba(des_array)[:, 1] for cf in cf_list]
            res[prop] = np.array(res_list).mean(0)
            if des_name == '2D':
                res[prop][inf_index] = np.nan
        else:
            raise Exception('Incorrect task type: ' + task_type)
        
    res['LogP'] = df_des['LogP'][start:end]
    # res['LogS'] = 10 ** res['LogS'] * df_des['MW'][start:end] * 1000
    res['LD50 of acute toxicity'] = 10 ** -res['LD50 of acute toxicity'] * df_des['MW'][start:end] * 1000
    res['Lipinski'] = lipinski(df_des[start:end])
    res['Ghose'] = ghose(df_des[start:end])
    res['Oprea'] = oprea(df_des[start:end])
    res['Veber'] = veber(df_des[start:end])
    res['Varma'] = varma(df_des[start:end], res)
    return res


chunk_size = args.chunk_size
chunk_size = min(chunk_size, len(df_des_name))
num_chunk = int(math.ceil(float(len(df_des_name)) / chunk_size))
print('num_chunk', num_chunk)

for i in range(num_chunk):
    chunk_start, chunk_end = i * chunk_size, min((i + 1) * chunk_size, len(df_des_name))
    real_chunk_size = chunk_end - chunk_start
    print('chunk_' + str(i) + ':', chunk_start, chunk_end)
    split_len = int(math.ceil(float(real_chunk_size) / args.threads))
    index_list = [(
        chunk_start + j * split_len, 
        min(chunk_start + (j + 1) * split_len, chunk_end)
    ) for j in range(args.threads)]
    print(index_list)
    # del df_des_name, name_dict
    
    pool = Pool(args.threads)
    res_list = pool.map(predict, index_list)
    pool.close()

    df_list = [pd.DataFrame(res) for res in res_list]
    df = pd.concat(df_list)

    smi_path = args.input_dir + '/admetlab_input_' + args.suffix + '.smi'
    name2smi = {}
    with open(smi_path) as f:
        lines = f.read().splitlines()
    for line in lines:
        smiles, name = line.split()
        name2smi[name] = smiles

    smiles_list = []
    for name in df_des_name[chunk_start:chunk_end]:
        smiles_list.append(name2smi[name])

    df.index = df_des.index[chunk_start:chunk_end]
    df.insert(0, 'smiles', smiles_list)
    res_path = '/admetlab_results_' + args.suffix + '_' + str(i) + '.csv' if args.suffix else '/admetlab_results_' + str(i) + '.csv'
    df.to_csv(args.output_dir + res_path)

all_results = []
for i in range(num_chunk):
    res_path = '/admetlab_results_' + args.suffix + '_' + str(i) + '.csv' if args.suffix else '/admetlab_results_' + str(i) + '.csv'
    df_chunk = pd.read_csv(args.output_dir + res_path, index_col=0)
    all_results.append(df_chunk)

df_all = pd.concat(all_results)
merged_path = '/admetlab_results_' + args.suffix + '.csv' if args.suffix else '/admetlab_results.csv'
df_all.to_csv(args.output_dir + merged_path)
