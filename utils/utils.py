import subprocess
import sys
import numpy as np

def run_command(command_list, step_name=""):
    """
    执行一个系统命令，并实时逐行打印其输出。
    如果命令失败，则打印错误并退出程序。
    """
    if step_name:
        print(f"--- Running Step: {step_name} ---")
    
    print(f"Executing command: {' '.join(command_list)}")

    try:
        # 使用 Popen 启动进程，并捕获输出管道
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 将错误输出合并到标准输出
            text=True,
            encoding='utf-8',
            bufsize=1  # 设置为行缓冲
        )

        # 实时读取并打印输出
        for line in process.stdout:
            sys.stdout.write(line)  # 使用 sys.stdout.write 避免 print 带来的额外换行
            sys.stdout.flush()      # 立即刷新缓冲区，确保内容显示出来

        process.wait()  # 等待子进程结束

        # 检查子进程的返回码
        if process.returncode != 0:
            print(f"\n\nError: Step '{step_name or ' '.join(command_list)}' failed with exit code {process.returncode}", file=sys.stderr)
            sys.exit(1)

    except FileNotFoundError:
        print(f"Error: Command not found -> '{command_list[0]}'. Please check if it's installed and in your PATH.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while running the command: {e}", file=sys.stderr)
        sys.exit(1)

    if step_name:
        print(f"--- Step '{step_name}' completed successfully. ---\n")


def zscore_sigmoid(series, reverse=False):
    """Applies z-score normalization followed by a sigmoid function to a pandas Series."""
    mu = series.mean()
    sigma = series.std()
    if sigma == 0:
        sigma = 1e-6  # Avoid division by zero
    z = (series - mu) / sigma
    if reverse:
        z = -z
    return 1 / (1 + np.exp(-z))