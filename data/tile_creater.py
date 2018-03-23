import numpy as np
def extract_raw_timeseres(quake_records):
    return np.vstack([quake['ts'] for quake in quake_records])
def tile_creater(manytimeseries,slicelen =1, metric = np.max):
    """manytimeseries is a list of dictionaries
    like so {'stationlat': , 'stationlon':, 'ts':numpy array}
    we need to calculate the metric for each one, and then place
    each metric in a 2d grid according to its latitude and longitude
    metric is a function that operates on a 2d array, and returns """
    dataarray = np.asarray([i['data'] for i in manytimeseries])#a n rows by t columns array where n is the num sensors
    metrics = slicecalcer(dataarray, slicelen, metric) #now columns are a metric of each slice of the original,
    #and rows still correspond with an individual sensor each. now for each column create a tile. something
    #like
    stationdeets = np.asarray([[i.get('stationlat'),i.get('stationlon')]
                                for i in manytimeseries])
    tiles = [singletile(metrics[:,idx], stationdeets)
             for idx in range(np.shape(metrics)[1])]
    return tiles
def singletile(metricslice, stationdeets):
    """create a tile from a column metricslice which has the metric value for
    #each station for r a given time slice. stationdeets is another numpy array
    which is n rows x 2, where each row is the lat, lon of the station at the corresponding
    row in metricslice:
    Return -> A 2d numpy array tile"""
    pass
def slicecalcer(dataarray, slicelen, metric):
    n,t=np.shape(dataarray)
    slice_steps = np.arange(0,t+1,slicelen)
    slices = [dataarray[:,i[0]:i[1]] for i in zip(slice_steps, slice_steps[1::])]
    metrics = np.asarray([metric(arr, axis=1) for arr in slices]).T
    return metrics
#probably best to create another function which returns grid values which we will use in tile_creater
#assuming we will use a square for now, can always change later
def grid_translation(topleft,stationlat, stationlon):
    """Args: 
    topleft is a tuple of the (lat, lon) of the most NW part of our grid
    stationlat,stationlon are the coordinates of the location we want translated
    Returns:
    (x,y) real valued x,y coordinates where 0<x<size, 0<y<size"""
    lon_ref = topleft[0]
    lat_ref = topleft[1]
    dx = (stationlon-lon_ref)
    dy = (lat_ref-stationlat)
    return (dx,dy)
def discretiser(plen_x, plen_y, x,y):
    """Args: 
    plen_x : pixel length(degree) in x dim
    plen_y : pixel length(degree) in y dim
    (x,y) real valued x,y coordinates where 0<x<size, 0<y<size
    Returns:
    (n,m) where n,m are integer valued pixel numbers e.g. (102,88)"""
    n = int(x/plen_x)
    m = int(y/plen_y)
    return (n,m)