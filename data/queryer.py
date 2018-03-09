import pandas as pd
import query_helpers
import helpers
import functools
import sqlite3
sqlconn = functools.partial(query_helpers.with_connection, sqlite3, 'groningendata.db')
def format_one_earthquake(lst):
	eventid, eventlat,eventlon, mag, concatted = lst
	return {'eventid':eventid,'eventlat':eventlat
			,'eventlon':eventlon,'magnitude':mag
			,'data':format_group(concatted)}
def format_group(rawgroup):
	lines = rawgroup.split('\n')
	splitline = lambda line: line.split('|')
	noop = lambda blob: blob
	processline = lambda lat,lon, ts: {'stationlat':lat,'stationlon':lon, 'ts':query_helpers.blob_to_arr(ts)}
	return [processline(*splitline(line)) for line in lines]

def get_earthquake_lazy(cnn):
	query = """SELECT g.eventid,e.latitude, e.longitude,e.magnitude,
				 group_concat(s.latitude|| '|' ||s.longitude|| '|' ||g.timeseries, '\n')
			FROM groundmotion g 
			INNER JOIN events e
			ON g.eventid = e.eventid
			INNER JOIN stations s
			on g.stationid = s.station
			GROUP BY g.eventid"""
	print('execing')
	cur = cnn.execute(query)
	print('execed')
	#res = helpers.parallel_map(format_one_earthquake, cur, chunksize=15)
	res = map(format_one_earthquake, cur)
	return res
def get_earthquake_eager(cnn):
	return list(get_earthquake_lazy(cnn))