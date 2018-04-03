import numpy as np
from . import helpers, queryer, query_helpers
import sqlite3
import functools
import itertools
import json
sqlconn = functools.partial(query_helpers.with_connection, sqlite3, 'data/groningendata.db')
def modify_short_timeseries(quake_records):
    maxlen = max([len(quake['ts']) for quake in quake_records ])
    onlylongquakes = [quake for quake in quake_records
                      if len(quake['ts']) == maxlen]
    return onlylongquakes
def gps_distance(latlon1, latlon2):
    from math import sin, cos, sqrt, atan2, radians
    # approximate radius of earth in km
    R = 6373.0
    lat1, lon1 = latlon1
    lat2, lon2 = latlon2
    lat1d = radians(lat1)
    lon1d = radians(lon1)
    lat2d = radians(lat2)
    lon2d = radians(lon2)
    dlon = lon2d - lon1d
    dlat = lat2d - lat1d
    a = sin(dlat / 2)**2 + cos(lat1d) * cos(lat2d) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance
def remove_outside_bounds(lats, lons, eles, lat_bound, lon_bound):
    """Args:
    lats: a float array of station latitudes
    lons: a float array of station longitudes
    lat_bound: a boolean function for filtering lats
    lon_bound: a boolean function for filtering lons
       
    Return:
    modified_lats: lats with any out of bounds removed
    modified_lons: lons with any out of bounds removed
    """
    inside_bounds = [(lat,lon, ele) for lat,lon, ele in zip(lats, lons,eles)
                     if lat_bound(lat) and lon_bound(lon)]
    return helpers.list_of_tuples_to_nlists(inside_bounds)

def filter_coords(candidatelist, keeper_coords):
    stations_matching_akeeper = [i for i in candidatelist
                    if any(coords_match(i, keeper_coords))]
    return stations_matching_akeeper
def coords_match(record, latloneles):
    def checker(record, latlonele): 
        latmatches = float(record['stationlat'])==latlonele[0]
        lonmatches = float(record['stationlon'])==latlonele[1]
        elematches = float(record['stationele'])==latlonele[2]
        return latmatches and lonmatches and elematches
    return [checker(record, i) for i in latloneles]
def remove_overlapping(lat, lon, ele):
    latlonele = zip(lat, lon, ele)
    getlatlon = lambda xyz: (xyz[0], xyz[1])
    inorder = sorted(latlonele, key = getlatlon)
    grouped = itertools.groupby(inorder, key= getlatlon)
    takehighest = lambda lst: max(lst, key = lambda x:x[2])
    justhighest = (takehighest(g) for k,g in grouped)
    return helpers.list_of_tuples_to_nlists(justhighest)
def remove_outlier(lat, lon, ele):
    notoutlier = [(lat, lon,ele) for lat,lon, ele
                 in zip(lat, lon, ele) if lat!=53.2135]
    return helpers.list_of_tuples_to_nlists(notoutlier)
def filter_outside_box(topleft, sizex, sizey, quake_data):
    all_lat = np.asfarray([station['stationlat'] for station in quake_data],float)
    all_lon = np.asfarray([station['stationlon'] for station in quake_data],float)
    all_ele = np.asfarray([station['stationele'] for station in quake_data],float)
    topright = (topleft[0]+sizex, topleft[1])
    bottomleft = (topleft[0], topleft[1]+sizey)
    inside_lat = lambda lat: lat < topleft[0] and lat > bottomleft[0]
    inside_lon = lambda lon: lon > topleft[1] and lon <topright[0]
    try:
        modified_lat, modified_lon, modified_ele =  remove_outside_bounds(all_lat,
            all_lon, all_ele, lambda lat: lat>53.0,lambda lon: lon>5.8)
        uqified_lat, uqified_lon, uqified_ele = remove_overlapping(modified_lat,
            modified_lon, modified_ele)
        manual_lat, manual_lon, manual_ele = remove_outlier(uqified_lat,
            uqified_lon, uqified_ele)
        filtered_data = filter_coords(quake_data,
            list(zip(manual_lat,manual_lon, manual_ele)))
        return filtered_data
    except ValueError:
        return []
    
def extract_raw_timeseries(quake_records, limit=24000):
    return np.vstack([quake['ts'][0:limit] for quake in quake_records])
def extract_station_deets(quake_records):
    stationdeets = np.asarray([[i.get('stationlat'),
                                i.get('stationlon')]
                                for i in quake_records], dtype=np.float64)
    return stationdeets
def tile_creater(manytimeseries,slicelen =1, metric = np.max):
    """manytimeseries is a list of dictionaries
    like so {'stationlat': , 'stationlon':, 'ts':numpy array}
    we need to calculate the metric for each one, and then place
    each metric in a 2d grid according to its latitude and longitude
    metric is a function that operates on a 2d array, and returns """
    dataarray = np.asarray([i['data'] for i in manytimeseries])
    #a n rows by t columns array where n is the num sensors
    metrics = slicecalcer(dataarray, slicelen, metric) 
    #now columns are a metric of each slice of the original,
    #and rows still correspond with an individual sensor each.
    stationdeets = np.asarray([[i.get('stationlat'),i.get('stationlon')]
                                for i in manytimeseries])
    tiles = [singletile(metrics[:,idx], stationdeets)
             for idx in range(np.shape(metrics)[1])]
    return tiles
def singletile(topleft, plen_x, plen_y, stationdeets, metricslice):
    """create a tile from a column metricslice which has the metric value for
    #each station for a given time slice. stationdeets is another numpy array
    which is n rows x 2, where each row is the lat, lon of the station at the
    corresponding row in metricslice:
    Return -> A 2d numpy array tile"""
    latlon_to_idxs = latlon_to_idxer(topleft, plen_x, plen_y)
    biggest = np.argmax(metricslice)
    sparse_rep = [(latlon_to_idxs(*stationdeets[i]), metricval) 
                   for i, metricval in enumerate(metricslice)]
    return sparse_rep
def latlon_to_idxer(topleft, plen_x,plen_y):
    translater = functools.partial(grid_translation, topleft)
    gridder = functools.partial(discretiser, plen_x, plen_y)
    latlon_to_idxs = helpers.pipe(translater, gridder)
    return latlon_to_idxs
def sparse_to_full(num_px, num_py, sparse_representation):
    empty_matrix = np.zeros((num_py, num_px))#beware the lat, lon: x,y confusion
    latlons = [latlon for latlon, val in sparse_representation]
    for (idxlat,idxlon), metricval in sparse_representation:
        empty_matrix[idxlon, idxlat] = metricval #beware the lat, lon: x,y confusion
    return empty_matrix
def zeromean(a, axis=1):
    avg = np.mean(a, axis =axis)
    res = (a.transpose() - avg).transpose()
    return res
def absmaxND(a, axis=None):
    amax = a.max(axis)
    amin = a.min(axis)
    return np.abs(np.where(-amin > amax, amin, amax))
def zeromeanpeak(a, axis=None):
    return np.max(zeromean(a, axis=1), axis=1)
def slicecalcer(slicelen, metric, dataarray):
    n,t=np.shape(dataarray)
    slice_steps = np.arange(0,t+1,slicelen)
    slices = [dataarray[:,i[0]:i[1]] for i 
              in zip(slice_steps, slice_steps[1::])]
    metrics = np.asarray([metric(arr, axis=1) for arr in slices]) 
    return metrics
#probably best to create another function which returns grid values which we 
#will use in tile_creater
#assuming we will use a square for now, can always change later
def grid_translation(topleft,stationlat, stationlon):
    """Args: 
    topleft is a tuple of the (lat, lon) of the most NW part of our grid
    stationlat,stationlon are the coordinates of the location we want translated
    Returns:
    (x,y) real valued x,y coordinates where 0<x<size, 0<y<size"""
    lat_ref = topleft[0]
    lon_ref = topleft[1]
    dx = (stationlon-lon_ref)
    dy = (lat_ref-stationlat)
    return dx,dy
def discretiser(plen_x, plen_y, xy):
    """Args: 
    plen_x : pixel length(degree) in x dim
    plen_y : pixel length(degree) in y dim
    (x,y) real valued x,y coordinates where 0<x<size, 0<y<size
    Returns:
    (n,m) where n,m are integer valued pixel numbers e.g. (102,88)"""
    x,y = xy
    n = int(x/plen_x)
    m = int(y/plen_y)
    return n,m
def get_pixel_lens(numx, numy, sizex, sizey):
    return sizex/numx, sizey/numy
def event_to_tiles(topleft,sizex, sizey, numx,numy, slicelen, oneevent):
    plenx, pleny = get_pixel_lens(numx, numy, sizex,sizey)
    no_shorts = modify_short_timeseries(oneevent['data'])
    no_outliers = filter_outside_box(topleft, sizex, sizey, no_shorts)
    if no_outliers:
        raw_timeseries = extract_raw_timeseries(no_outliers, limit = slicelen*20)
        print(np.shape(raw_timeseries))
        stationdeets = extract_station_deets(no_outliers)
        #build the pipeline
        metriciser = functools.partial(slicecalcer, slicelen, zeromeanpeak)
        onetiler = functools.partial(singletile, topleft, plenx, pleny, stationdeets)
        matrixifier = functools.partial(sparse_to_full, numx, numy)
        metricslice_to_tile = helpers.pipe(onetiler, matrixifier)
        manytiler = functools.partial(map, metricslice_to_tile)
        data_to_tiles = helpers.pipe(metriciser, manytiler)
        return list(data_to_tiles(raw_timeseries))
    else:
        return no_outliers
def num_nonzeros(arr):
    return len(nonzeroidxs(arr))
def nonzeroidxs(arr):
    return list(zip(*np.nonzero(arr)))
def earthquake_to_training_and_label(topleft,sizex, sizey, numx,numy, slicelen, oneevent):
    trainingdata = event_to_tiles(topleft,sizex, sizey, numx,numy,
                                  slicelen, oneevent)
    label = (oneevent['eventlat'],oneevent['eventlon']
            ,oneevent['eventdepth'], oneevent['magnitude']
            ,oneevent['eventid'], topleft, sizex, sizey, numx,numy)
    return label, trainingdata
def tile_to_file(label, tile, seq):
    eventid = label[4]
    name = './data/tiles/{}.txt'.format(eventid+'_'+str(seq))
    nonzeros = num_nonzeros(tile)
    tmp = list(label)
    tmp.append(nonzeros)
    label_nz = tuple(tmp)
    np.savetxt(name, tile)
    try:
        with open('./data/tiles/metadata.json','r+') as f:
            already = json.load(f)
    except FileNotFoundError as e:
        already = {}
    if eventid not in already:
        print('nonzeros: ', nonzeros)
        already[eventid] = label_nz
    with open('./data/tiles/metadata.json', "w+") as f:
        json.dump(already, f)
def write_earthquake_egs_tofile(oneevent):
    topleft = (53.5, 6.4)
    sizex = 1
    sizey = 0.5
    numx= 60
    numy = 30
    slicelen=50

    label, tiles = earthquake_to_training_and_label(topleft,sizex, sizey, numx,numy, slicelen, oneevent)
    for idx, tile in enumerate(tiles):
        print('event: {}, number {}'.format(oneevent['eventid'], idx))
        tile_to_file(label, tile, idx)

@sqlconn
def stream_to_file(cnn):
    quake_stream = queryer.get_earthquake_lazy(cnn)
    enoughsensors = (q for q in quake_stream if len(q['data'])>100)
    for idx, quake_record in enumerate(enoughsensors):
        print(np.shape(quake_record['data']))
        print('processing quake num {}'.format(idx))
        write_earthquake_egs_tofile(quake_record)
    return
if __name__=='__main__':
    stream_to_file()






