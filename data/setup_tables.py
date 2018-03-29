import query_helpers
import sqlite3
import functools
import pandas as pd
import numpy as np
import json
dbname = 'groningendata.db'
sqlconn = functools.partial(query_helpers.with_connection, sqlite3,dbname)

@sqlconn
def setup_events(cnn):
	url = 'http://rdsa.knmi.nl/fdsnws/event/1/query?format=text&nodata=404'
	df = pd.read_csv(url,sep='|')
	df.columns=df.columns.str.replace('#','')
	df.columns = df.columns.str.replace('/','')
	query_helpers.df_to_sqlite(cnn,df,'events')
	df.to_csv('events.csv', index=False)
	cnn.execute('''CREATE INDEX eventsidx ON events (eventid)''')
def correct_niveau_elevations(df):
	df.loc[df['SiteName'].str.contains("niveau 0"), 'Elevation'] = 0
	df.loc[df['SiteName'].str.contains("niveau 1"), 'Elevation'] = -50
	df.loc[df['SiteName'].str.contains("niveau 2"), 'Elevation'] = -100
	df.loc[df['SiteName'].str.contains("niveau 3"), 'Elevation'] = -150
	df.loc[df['SiteName'].str.contains("niveau 4"), 'Elevation'] = -200
	df.loc[df['SiteName'].str.contains("niveau 5"), 'Elevation'] = -250
	return df
@sqlconn
def setup_stations(cnn):
	url = 'http://rdsa.knmi.nl/fdsnws/station/1/query?format=text&nodata=404'
	df = pd.read_csv(url,sep='|')
	df.columns=df.columns.str.replace('#','')
	df = correct_niveau_elevations(df)
	query_helpers.df_to_sqlite(cnn,df,'stations')
	df.to_csv('stations.csv', index=False)
	cnn.execute('''CREATE INDEX stationssidx ON stations (station)''')
@sqlconn
def setup_groundmotion(cnn):
	cur = cnn.cursor()
	cur.execute('''CREATE TABLE groundmotion 
		(eventid text, stationid text, channel text, timeseries BLOB,
		 startime text, endtime text, exactstart text, exactend text,
		 PRIMARY KEY (eventid, stationid, channel),
		 FOREIGN KEY (eventid) REFERENCES events (eventid),
		 FOREIGN KEY (stationid) REFERENCES stations (station)
		 )''')
	cur.execute('''CREATE INDEX groundeventsidx ON groundmotion (eventid)''')
if __name__=='__main__':
	setup_stations()
	setup_events()
	setup_groundmotion()
