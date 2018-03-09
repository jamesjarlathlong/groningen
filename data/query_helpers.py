import sqlite3
import pandas as pd
import json
import numpy as np
from tqdm import tqdm
def with_connection(mod, db_filename, f):
    def with_connection_(*args, **kwargs):
        # or use a pool, or a factory function...
        cnn = mod.connect(db_filename)
        try:
            rv = f(cnn, *args, **kwargs)
        except Exception as e:
            cnn.rollback()
            raise
        else:
            cnn.commit() # or maybe not
        finally:
            cnn.close()
        return rv
    return with_connection_
def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))
def df_to_sqlite(cnn, df, tablename):
    chunksize = int(len(df) / 100) # 1%
    with tqdm(total=len(df)) as pbar:
        for i, cdf in enumerate(chunker(df, chunksize)):
            replace = "replace" if i == 0 else "append"
            cdf.to_sql(con=cnn, name=tablename, if_exists=replace, index=False)
            pbar.update(chunksize)
def arr_to_blob(arr):
    return json.dumps(arr.tolist())
def blob_to_arr(blob):
    return np.asarray(json.loads(blob))