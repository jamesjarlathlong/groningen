import functools
import itertools
import collections
import asyncio
import concurrent
import time
def bind(f):
    def wrapper(x):
        if x is None:
            return None
        else:
            return f(x)
    return wrapper
def compose_two(func1, func2):
     def composition(*args, **kwargs):
        return func1(func2(*args, **kwargs))
     return composition
def compose(*funcs):
    return functools.reduce(compose_two, funcs)
def pipe(*funcs):
    return functools.reduce(compose_two, reversed(funcs))
def dict_product(d):
    """e.g.d = {'A':[0,1]
                ,'B':[3]}
    return [{'A':0, 'B':3}
            {'A':1,'B':3}]"""
    ks = d.keys()#e.g. ['A,'B']
    values = d.values() #e.g. [[0,1],[3]]
    products = itertools.product(*values) #e.g. ...[(0,3),(1,3)]
    zipped = (zip(ks, product) for product in products) #e.g.[ [('A",0),('B',3)],[('A",1),('B',3)]]
    return (dict(tpl) for tpl in zipped)
def merge_dicts(*dcts):
    return dict(collections.ChainMap({}, *dcts))
many_dict_product = pipe(merge_dicts, dict_product)

def list_of_tuples_to_nlists(lst):
    return list(zip(*lst))
    
def lstdcts2dctlsts(lst):
    """e.g. [{'A':2},{'A':3}] -> {'A':[2,3]}"""
    def accumer(accum, el):
        for k,v in el.items():
            accum[k].append(v)
        return accum
    return dict(functools.reduce(accumer, lst, collections.defaultdict(list)))
def first_n(seq, n):
    return (x for _,x in zip(range(n), seq))
def grouper(n, iterable):
    """
    >>> list(grouper(3, 'ABCDEFG'))
    [['A', 'B', 'C'], ['D', 'E', 'F'], ['G']]
    """
    iterable = iter(iterable)
    return iter(lambda: list(itertools.islice(iterable, n)), [])
async def parallelmain(curriedjobs, workers=20):
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        loop = asyncio.get_event_loop()
        futures = [loop.run_in_executor(executor, f) for f in curriedjobs]
        all_res = [response for response in await asyncio.gather(*futures)]
        return all_res
def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print('%r  %2.2f ms' % \
                  (method.__name__, (te - ts) * 1000))
        return result

    return timed
def run_parallel(curriedjobs, workers=20):
    loop = asyncio.get_event_loop()
    all_res = loop.run_until_complete(parallelmain(curriedjobs, workers))
    return all_res
def run_chunks_parallel(jobs,chunksize = 100, workers = 20):
    chunked = grouper(chunksize,jobs)
    res_chunks = (run_parallel(chunk, workers=workers) for chunk in chunked)
    flat_res = itertools.chain(*res_chunks)
    return flat_res