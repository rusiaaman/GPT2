import argparse
import glob
import os
import time
from multiprocessing import Pool

import ftfy
import numpy as np
import tensorflow as tf
from tqdm import tqdm

import encoder

def _int64_feature(value):
    """Returns an int64_list from a bool / enum / int / uint."""
    return tf.train.Feature(int64_list=tf.train.Int64List(value=value))

def _bytes_feature(value):
  """Returns a bytes_list from a string / byte."""
  return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

# Divides a list into chunks
def chunks(l, n):
    out = []
    for i in range(0, len(l), n):
        out.append(l[i:i + n])
    return out

def create_file(args):
    i, chunk = args
    s = name + "_" + str(i) + ".tfrecords"
    if os.path.exists(os.path.join(log_dir, s)): # Hack-y, if file of same name is in log dir, sign that the file is complete, so skip
        return
    if os.path.exists(os.path.join(output_dir, s)): # Unfinished file, remove
        os.remove(os.path.join(output_dir, s))
    
    with tf.python_io.TFRecordWriter(os.path.join(output_dir, s)) as writer:
        good_files = 0
        current = None
        for fn in chunk:
            with tf.gfile.Open(fn, "r") as f:
                d = f.read()
            d = ftfy.fix_text(d, normalization='NFKC')
            data = np.array(enc.encode(d), np.int32)
            if data.shape[0] < 25 or (data == 0).all(): # If text is shorter than 25 tokens, or all tokens are 0, ignore
                continue
            hash = fn.split("/")[-1].split(".")[0]
            feature = {
                "hash": _bytes_feature(hash.encode()),
                "text": _int64_feature(data)
            }
            tf_example = tf.train.Example(features=tf.train.Features(feature=feature))
            writer.write(tf_example.SerializeToString())
            good_files += 1
    # File complete
    with open(os.path.join(log_dir, s), "w") as f: # Create mark that file is finished in logdir
        f.write("{} / {}".format(str(good_files), str(len(chunk))))
    with open(os.path.join(log_dir, "good_files.log"), "a") as f:
        f.write("{}: {} / {}".format(str(i), str(good_files), str(len(chunk))))

    return good_files

if __name__=="__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_dir",help="Path to where your .txt files are located",type=str)
    parser.add_argument("--files_per",help="Number of files per tf record",default=175000,type=int)
    parser.add_argument("--name",help="Output file name prefix {name}_i.tfrecords where i is the"
                                "index of file",default="openwebtext-newspaper",type=str)
    
    parser.add_argument("--output_dir",help="Output directory",default="out",type=str)
    parser.add_argument("--log_dir",help="Log directory",default="logs",type=str)
    parser.add_argument("--processes",help="Number of encoding processes to run",default=64,type=int)
    parser.add_argument("--encoder_path",help="Path to encoder files",default="encoder",type=str)
    
    args = parser.parse_args()
    
    name = args.name # Name of output files will be name_i.tfrecords where i is the number of the file
    output_dir = args.output_dir
    log_dir = args.log_dir
    files = glob.glob(os.path.join(args.base_dir, "**/*.txt"))

    if not os.path.exists(log_dir):
        os.mkdir(log_dir)

    enc = encoder.get_encoder(args.encoder_path)

    file_chunks = chunks(files, args.files_per)

    print("Got {} files, divided into {} chunks.".format(str(len(files)), str(len(file_chunks))))



    start = time.time()
    pool = Pool(processes=args.processes)
    good = 0
    for g in tqdm(pool.imap(create_file, enumerate(file_chunks)), total=len(file_chunks)):
        good += g

    end = time.time()

    print("Done! In {:.2f}s, {} / {} good files.".format(end-start, str(good), str(len(files))))
