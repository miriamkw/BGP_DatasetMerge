import os
import sys
import tempfile
import subprocess
from tqdm import tqdm
from collections import Counter
import math
import click


def estimate_true_information(path, temp_dir=None):
    """
    Estimate true information content using zstd compression.
    Returns compressed size in bytes.
    """
    if temp_dir is None:
        temp_dir = tempfile.gettempdir()

    temp_archive = os.path.join(temp_dir, 'temp_archive.zst')

    try:
        if os.path.exists(temp_archive):
            os.remove(temp_archive)

        print("Compressing data...")
        # Compress the directory/file using zstd with maximum compression
        if os.path.isdir(path):
            cmd = f'tar -cf - -C "{os.path.dirname(path)}" "{os.path.basename(path)}" | zstd -22 --force -o "{temp_archive}"'
            print(f"Running command: {cmd}")
            subprocess.run(cmd, shell=True, check=True, stderr=subprocess.PIPE)
        else:
            subprocess.run(
                ['zstd', '-22', '--force', '-o', temp_archive, path],
                check=True,
                stderr=subprocess.PIPE,
                text=True
            )

        compressed_size = os.path.getsize(temp_archive)
        return compressed_size

    except subprocess.CalledProcessError as e:
        print(f"Compression error: {e.stderr}")
        raise
    finally:
        if os.path.exists(temp_archive):
            os.remove(temp_archive)


def calculate_file_entropy(filename):
    """
    Calculate the entropy of a file in bits per byte, with a progress bar.

    Parameters:
    filename (str): The path to the file.

    Returns:
    float: The entropy value.
    """
    file_size = os.path.getsize(filename)
    if file_size == 0:
        return 0.0  # Handle empty file

    byte_counts = Counter()
    total_bytes = 0

    with open(filename, 'rb') as f, tqdm(total=file_size, unit='B', unit_scale=True, desc='Processing') as pbar:
        while True:
            chunk = f.read(65536)  # Read in chunks of 64KB
            if not chunk:
                break
            byte_counts.update(chunk)
            bytes_read = len(chunk)
            total_bytes += bytes_read
            pbar.update(bytes_read)

    entropy = 0.0
    for count in byte_counts.values():
        p_x = count / total_bytes
        entropy -= p_x * math.log2(p_x)
    return entropy


def process_path(path):
    """
    Process a file or directory and estimate true information content.
    """
    if not os.path.exists(path):
        raise ValueError(f"Path {path} does not exist")

    # Calculate original size with progress bar for directories
    if os.path.isfile(path):
        size = os.path.getsize(path)
    else:
        print("Calculating total size...")
        size = 0
        for root, _, files in os.walk(path):
            for file in files:
                try:
                    size += os.path.getsize(os.path.join(root, file))
                except (OSError, PermissionError) as e:
                    print(f"Warning: Couldn't access {file}: {e}")

    print(f"\nAnalyzing: {path}")
    print(f"Original size: {size / 1000000:.2f} MB")

    print("Computing true information content...")
    compressed_size = estimate_true_information(path)

    print(f"Compressed size: {compressed_size / 1000000:.2f} MB")
    print(f"True information content (est.): {compressed_size * 8 / 1000000000:.2f} GB")

    if size > 0:
        compression_ratio = (size - compressed_size) / size * 100
        print(f"Compression ratio: {compression_ratio:.1f}%")


@click.group()
def cli():
    """
    Analyze information content of files and directories using different methods.

    This tool provides two different approaches to estimate information content:

    1. Compression-based estimation (compress command):
       Uses zstd compression to estimate true information content.
       Works with both files and directories.

    2. Shannon entropy calculation (entropy command):
       Calculates entropy in bits per byte using Shannon's entropy formula.
       Works with files only.
    """
    pass


@cli.command()
@click.argument('path', type=click.Path(exists=True))
def compress(path):
    """
    Estimate information content using compression.

    This command uses zstd compression (level 22) to estimate the true information
    content of files or directories. It works by:

    1. Calculating the original size
    2. Compressing the data using maximum compression
    3. Measuring the compressed size
    4. Computing the compression ratio

    The compressed size provides an upper bound for the true information content.
    """
    try:
        process_path(path)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
def entropy(path):
    """
    Calculate Shannon entropy of a file.

    This command analyzes a file byte by byte to calculate its Shannon entropy,
    which measures the average information content per byte. The calculation:

    1. Counts frequency of each byte value
    2. Calculates probability distribution
    3. Computes entropy using Shannon's formula: -sum(p * log2(p))

    The result is in bits per byte (0-8). Higher values indicate more random/compressed data.
    Note: This command works only on individual files, not directories.
    """
    try:
        entropy_value = calculate_file_entropy(path)
        size = os.path.getsize(path)
        click.echo(f"\nAnalyzing: {path}")
        click.echo(f"File size: {size / 1000000:.2f} MB")
        click.echo(f"Entropy: {entropy_value:.2f} bits per byte")
        click.echo(f"Total information content (est.): {(size * entropy_value) / 8000000000:.2f} GB")
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()