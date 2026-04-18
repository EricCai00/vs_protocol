#!/public/home/caiyi/software/miniconda3/envs/python39/bin/python

import argparse

if __name__ == '__main__':
    import sys
    sys.path.append('/public/home/caiyi/eric_github/vs_protocol/')
    from deduplicate import deduplicate
    from admetlab_descriptors import admetlab_descriptors
    from generate_fp import batch_generate_fp
else:
    from .deduplicate import deduplicate
    from .admetlab_descriptors import admetlab_descriptors
    from .generate_fp import batch_generate_fp


def admetlab_prepare(input_, wd, suffix, threads):
    deduplicate(
        input_=input_, 
        output=f'{wd}/admetlab_input_{suffix}.smi'
        )
    
    admetlab_descriptors(
        input_=f'{wd}/admetlab_input_{suffix}.smi',
        output=f'{wd}/descriptors_{suffix}.csv',
        threads=threads
        )
        
    batch_generate_fp(
        input_=f'{wd}/admetlab_input_{suffix}.smi',
        output=f'{wd}/MACCS_{suffix}.h5',
        fp_type='maccs_full',
        threads=threads
    )
        
    batch_generate_fp(
        input_=f'{wd}/admetlab_input_{suffix}.smi',
        output=f'{wd}/ECFP2_2048_{suffix}.h5',
        fp_type='ecfp2_2048',
        threads=threads
    )
        
    batch_generate_fp(
        input_=f'{wd}/admetlab_input_{suffix}.smi',
        output=f'{wd}/ECFP4_2048_{suffix}.h5',
        fp_type='ecfp4_2048',
        threads=threads
    )
        
    batch_generate_fp(
        input_=f'{wd}/admetlab_input_{suffix}.smi',
        output=f'{wd}/ECFP4_1024_{suffix}.h5',
        fp_type='ecfp4_1024',
        threads=threads
    )
        
    batch_generate_fp(
        input_=f'{wd}/admetlab_input_{suffix}.smi',
        output=f'{wd}/ECFP6_2048_{suffix}.h5',
        fp_type='ecfp6_2048',
        threads=threads
    )

if __name__ == '__main__':
    
    usage = ('admetlab_des.py --input <smi_file> --output <csv_file> --threads 20\n\n'
    'Example: admetlab_des.py -i /public/home/caiyi/data/docking/DeepDocking/projects/test_fp/iteration_1/smile/admetlab_test.smi -t 20')

    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument('-i', '--input', required=True)
    parser.add_argument('-d', '--wd', required=True)
    parser.add_argument('-s', '--suffix', required=True)
    parser.add_argument('-t', '--threads', default=1, type=int)
    args = parser.parse_args()

    admetlab_prepare(args.input, args.wd, args.suffix, args.threads)
