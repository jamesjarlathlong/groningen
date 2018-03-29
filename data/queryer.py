import pandas as pd
from . import query_helpers, helpers
import functools
import sqlite3
sqlconn = functools.partial(query_helpers.with_connection, sqlite3, 'data/groningendata.db')
def format_one_earthquake(lst):
	eventid, eventlat,eventlon, mag,depthkm, concatted = lst
	return {'eventid':eventid,'eventlat':eventlat
			,'eventlon':eventlon,'magnitude':mag
			,'eventdepth':depthkm,'data':format_group(concatted)}
def format_group(rawgroup):
	lines = rawgroup.split('\n')
	splitline = lambda line: line.split('|')
	noop = lambda blob: blob
	def processline(lat,lon,ele, ts):
		return {'stationlat':lat,'stationlon':lon,
				'stationele':ele,'ts':query_helpers.blob_to_arr(ts)}
	return [processline(*splitline(line)) for line in lines]

def get_earthquake_lazy(cnn):
	query = """SELECT g.eventid,e.latitude, e.longitude,e.magnitude,e.depthkm,
				 group_concat(s.latitude|| '|' ||s.longitude|| '|' ||
				 			  s.elevation|| '|' || g.timeseries, '\n')
			FROM groundmotion g 
			INNER JOIN events e
			ON g.eventid = e.eventid
			INNER JOIN stations s
			on g.stationid = s.station
			GROUP BY g.eventid"""
	cur = cnn.execute(query)
	#res = helpers.parallel_map(format_one_earthquake, cur, chunksize=15)
	res = map(format_one_earthquake, cur)
	return res
@sqlconn
def get_earthquake_eager(cnn):
	return list(get_earthquake_lazy(cnn))
