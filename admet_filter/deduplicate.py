#!/public/home/caiyi/software/miniconda3/envs/python39/bin/python
import argparse

def deduplicate(input_, output):
    with open(input_) as f:
        lines = f.read().splitlines()

    s = set()
    with open(output, 'w') as f:
        for line in lines:
            smi, name = line.split()
            if name in s:
                continue
            else:
                s.add(name)
                f.write(f'{line}\n')

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True)
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()

    deduplicate(args.input, args.output)
