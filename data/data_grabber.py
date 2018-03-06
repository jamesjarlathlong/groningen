import obspy
import requests
import io
import matplotlib
import pandas as pd
import helpers
import functools
import datetime
import copy
import sys
import sqlite3
sqlconn = functools.partial(helpers.with_connection, sqlite3, 'groningendata.db')
def get_event_response(network=None, station=None, channel=None,
					   eventid=None,starttime=None, endtime=None):
    """get an event mseed file from the knmi database given
    query parameters describing the event"""
    baseurl = 'http://rdsa.knmi.nl/fdsnws/dataselect/1/query'
    payload = {'starttime':starttime,'endtime':endtime,'network':network,
               'station':station, 'channel':channel,'nodata':404}
    r = requests.get(baseurl,params=payload)
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
@helpers.bind
def stream_formatter(streamified):
	"""murat fill in here"""
	streamified['timeseries'] = streamified['stream'][0][0:2]
	streamified['exactstart']='dummy'
	streamified['exactend']='dummy'
	return streamified
def add_to_timestring(nseconds, isostring):
	"""given a timestamp in iso8601 string format, add a timedelta
	of nseconds to the time and return
	a new iso8601 string with the incremented time."""
	currenttime = datetime.datetime.strptime(isostring,"%Y-%m-%dT%H:%M:%S.%f")
	delta = datetime.timedelta(seconds=nseconds)
	futuretime = currenttime+delta
	return datetime.datetime.strftime(futuretime,"%Y-%m-%dT%H:%M:%S.%f")
def parse_events(f='events.csv', incrementer = functools.partial(add_to_timestring,300)):
	df = pd.read_csv(f, delimiter = ',',encoding='utf-8')[['EventID','Time']]
	return ({'event':{'eventid':eventid,'starttime':time, 'endtime':incrementer(time)}} for index,eventid,time in df.itertuples())

get_and_streamify = helpers.pipe(get_event_response, streamify) #pipe(f,g)() is equivalent to f(g())
get_and_format = helpers.pipe(get_event_response, streamify, stream_formatter)
def unroll(job_d):
	event_d =job_d['event']
	del job_d['event']
	return helpers.merge_dicts(job_d, event_d)
def create_jobs_queue(limit = 5):
	"""create a generator of job parameter dicts like:
	[{'starttime':s,'endtime':e,'network':n,
               'station':s, 'channel':c},,,"""
	n = {'network': ['NL']}
	stations = {'station':['VKB']}
	channels = {'channel':['BHZ']}
	events = helpers.lstdcts2dctlsts(helpers.first_n(parse_events(), limit))
	all_combs = helpers.many_dict_product(n, stations, channels, events)
	return map(unroll,all_combs)

def serial_worker(jobs_queue):
	"""given an iterator of event dictionaries 
	{'starttime':s,'endtime':e,'network':n,
     'station':s, 'channel':c}
	get the http response for that set of parameteres,,
	extract the mseed stream and format it."""
	return (get_and_format(**job) for job in jobs_queue)
def parallel_worker(jobs_queue):
	"""multithreaded concurrent version of serial worker"""
	jobs = (functools.partial(get_and_format, **job) for job in jobs_queue)
	res = helpers.run_chunks_parallel(jobs, chunksize = 10)
	return res
def res_prep(res):
	tpl= (res['_id'], res['station'],res['channel'], 
			helpers.arr_to_blob(res['timeseries']), 
			res['starttime'],res['endtime'],res['exactstart'],res['exactend'])
	print('tpl: ', tpl)
	return tpl
@sqlconn
def write_to_db(cnn, res_chunk):
	insert_q = """INSERT INTO groundmotion(eventid, stationid, channel, timeseries,
					startime, endtime, exactstart, exactend)
					VALUES(?, ?, ?, ?, ?, ?, ?, ?)"""
	cnn.executemany(insert_q, map(res_prep,res_chunk))
if __name__ == '__main__':
	q = create_jobs_queue(limit = 10)
	res = parallel_worker(q)
	for r in helpers.grouper(4,res):
		write_to_db(r)