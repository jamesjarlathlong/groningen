import obspy
import requests
import io
import pandas as pd
import helpers
import functools
import itertools
import datetime
import copy
import sys
import sqlite3
import query_helpers
sqlconn = functools.partial(query_helpers.with_connection, sqlite3, 'groningendata.db')
def get_event_response(network=None, station=None, channel=None,
                       eventid=None,starttime=None, endtime=None):
    """get an event mseed file from the knmi database given
    query parameters describing the event"""
    baseurl = 'http://rdsa.knmi.nl/fdsnws/dataselect/1/query'
    payload = {'starttime':starttime,'endtime':endtime,'network':network,
               'station':station, 'channel':channel,'nodata':404}
    r = requests.get(baseurl,params=payload)
    print('http response received')
    if r.status_code ==200:
        return {'data':r.content,'starttime':starttime,'endtime':endtime
                ,'channel':channel,'station':station, '_id':eventid}
@helpers.bind
def streamify(event_response):
    data = event_response['data']
    st = obspy.read(io.BytesIO(data))
    useful_keys = ['starttime','endtime','channel','station','_id']
    streamified = {'stream':st}
    for k in useful_keys:
        streamified[k]=event_response[k]
    return streamified

def stream_trimmer(untrimmed_stream,start_time,end_time):
    """
    args:
    untrimmed stream is an obspy object, containing exactly one trace
    start_time is the time string we desire the stream start to be trimmed to
    end_time is the time string we desire the stream end to be trimmed to 
    """
    start_dt = obspy.core.utcdatetime.UTCDateTime(start_time)
    end_dt = obspy.core.utcdatetime.UTCDateTime(end_time)
    trace_in = untrimmed_stream[0]
    trace_in.trim(start_dt,end_dt)
    exactstart=str(obspy.core.utcdatetime.UTCDateTime(trace_in.stats.starttime))
    exactend=str(obspy.core.utcdatetime.UTCDateTime(trace_in.stats.endtime))
    return trace_in.data, exactstart, exactend
@helpers.bind
def stream_formatter(streamified):
    """murat fill in here"""
    trimmed, exactstart,exactend = stream_trimmer(streamified['stream'],
        streamified['starttime'], streamified['endtime'])
    streamified['timeseries'] = trimmed
    streamified['exactstart'] = exactstart
    streamified['exactend']= exactend
    return streamified
def add_to_timestring(nseconds, isostring):
    """given a timestamp in iso8601 string format, add a timedelta
    of nseconds to the time and return
    a new iso8601 string with the incremented time."""
    currenttime = datetime.datetime.strptime(isostring,"%Y-%m-%dT%H:%M:%S.%f")
    delta = datetime.timedelta(seconds=nseconds)
    futuretime = currenttime+delta
    return datetime.datetime.strftime(futuretime,"%Y-%m-%dT%H:%M:%S.%f")
def parse_events(f='events.csv', incrementer = functools.partial(add_to_timestring,120)):
    df = pd.read_csv(f, delimiter = ',',encoding='utf-8')[['EventID','Time']]
    return ({'event':{'eventid':eventid,'starttime':time, 'endtime':incrementer(time)}} for index,eventid,time in df.itertuples())

get_and_streamify = helpers.pipe(get_event_response, streamify) #pipe(f,g)() is equivalent to f(g())
get_and_format = helpers.pipe(get_event_response, streamify, stream_formatter)
def unroll(job_d):
    event_d =job_d['event']
    del job_d['event']
    return helpers.merge_dicts(job_d, event_d)
def get_stations():
    return pd.read_csv('stations.csv')['Station'].tolist()
def create_jobs_queue(limit = None):
    """create a generator of job parameter dicts like:
    [{'starttime':s,'endtime':e,'network':n,
               'station':s, 'channel':c},,,"""
    n = {'network': ['NL']}
    stations = {'station':get_stations()}
    channels = {'channel':['HHZ']}
    events = helpers.lstdcts2dctlsts(parse_events())
    all_combs = helpers.many_dict_product(n, stations, channels, events)
    first_n = helpers.first_n(all_combs,limit) if limit else all_combs
    return map(unroll,first_n)

def serial_worker(jobs_queue):
    """given an iterator of event dictionaries 
    {'starttime':s,'endtime':e,'network':n,
     'station':s, 'channel':c}
    get the http response for that set of parameteres,,
    extract the mseed stream and format it."""
    return (get_and_format(**job) for job in jobs_queue)

@helpers.timeit
def parallel_worker(jobs_queue):
    """multithreaded concurrent version of serial worker"""
    jobs = (functools.partial(get_and_format, **job) for job in jobs_queue)
    res = helpers.run_chunks_parallel(jobs, chunksize = 20, workers = 20)
    return res
def res_prep(res):
    tpl= (res['_id'], res['station'],res['channel'], 
            query_helpers.arr_to_blob(res['timeseries']), 
            res['starttime'],res['endtime'],res['exactstart'],res['exactend'])
    return tpl
@sqlconn
def write_to_db(cnn, res_chunk):
    insert_q = """INSERT INTO groundmotion(eventid, stationid, channel, timeseries,
                    startime, endtime, exactstart, exactend)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)"""
    cnn.executemany(insert_q, (res_prep(r) for r in res_chunk if r))
@sqlconn
def filter_dones(cnn, q):
    query = """select startime, endtime, stationid, channel from groundmotion"""
    alldone = set((i for i in cnn.execute(query)))
    def tuplify(qitem):
        keys=['starttime','endtime','station','channel']
        return tuple((qitem[k] for k in keys)) 
    return (i for i in q if tuplify(i) not in alldone)
if __name__ == '__main__':
    allq = create_jobs_queue(limit = None)
    q = filter_dones(allq)
    qcopy, jobq = itertools.tee(q)
    n = sum((1 for _ in qcopy))
    print('filtered, starting to make requests to remote')
    for i, qchunk in enumerate(helpers.grouper(20, jobq)):
        res = parallel_worker(qchunk)
        print('writing chunk {} of {} to db'.format(i, n/20))
        write_to_db(res)
