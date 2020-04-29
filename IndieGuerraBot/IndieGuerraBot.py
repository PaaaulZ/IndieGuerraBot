import requests
import json
import os
import mysql.connector
import hashlib
import logging
import random
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

def load_config():

    if not os.path.exists('config.json'):
        log.info("Cannot find config.json")
        exit()

    f_config = open('config.json','r')

    return json.load(f_config)

config = load_config()
fh = logging.FileHandler('indieguerrabot.log')
log = logging.getLogger('IndieGuerraBot')

def main():

    logging.basicConfig(format='%(asctime)s - [%(levelname)s]: %(message)s')
    log.setLevel(logging.DEBUG)
    log.addHandler(fh)

    update_score()
    generate_owners()
    result_json = json_for_map()
    download_map(result_json)

def getlocation_ID(cityName):

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    my_cursor = mydb.cursor()
    my_cursor.execute("SELECT id FROM locations WHERE city = '" + cityName + "'")

    location_ID = -1
    for res in my_cursor:
        location_ID = res[0]
        break
    
    mydb.close()
    
    return location_ID

def getspotify_album_ID(artist,track,next = ''):

    if next is None or next == '':
        url = f"https://api.spotify.com/v1/search?q={track.lower().rstrip()} {artist}&type=track&limit=50"
    else:
        url = next
    
    r = requests.get(url, headers={"Accept":"application/json","Content-Type":"application/json","Authorization":"Bearer " + config['spotifyApiKey']})
    if r.status_code != 200:
        log.warning(f"Unable to search {artist} - {track} from Spotify {r.status_code}")
        return "NO_MATCH"
        #exit()

    tracks_json = json.loads(r.text)

    for i in range(len(tracks_json['tracks']['items'])):       

        # Check if artist present
        for j in range(len(tracks_json['tracks']['items'][i]['artists'])):
            if tracks_json['tracks']['items'][i]['artists'][j]['name'].lower().rstrip() == artist.lower().rstrip().encode('utf-8').decode('utf-8') or artist.lower().rstrip().encode('utf-8').decode('utf-8') in tracks_json['tracks']['items'][i]['name'] or artist.lower().rstrip().encode('utf-8').decode('utf-8') in tracks_json['tracks']['items'][i]['artists'][j]['name'].lower().rstrip():
                return tracks_json['tracks']['items'][i]['album']['id']

        #if tracks_json['tracks']['next'] != '':
        #    getspotify_album_ID(artist,track,tracks_json['tracks']['next'])

    return "NO_MATCH"

def get_play_count(artist,track):

    spotify_album_ID = getspotify_album_ID(artist,track)

    if spotify_album_ID == 'NO_MATCH':
        log.info(f"NO ALBUM ID FOR {track} BY {artist}")
        return -1

    r = requests.get(f"https://api.t4ils.dev/albumPlayCount?albumid={spotify_album_ID}")
    if r.status_code != 200:
        log.warning(f"Unable to get playcount for {track} by {artist} ({r.status_code})")
        return -2

    album_play_count_json = json.loads(r.text)

    if not album_play_count_json['success']:
        log.info(f"Cannot get album play_count for {artist}/{track}/{spotify_album_ID}")
        return -2
    
    for i in range(len(album_play_count_json['data']['discs'])):
        for j in range(len(album_play_count_json['data']['discs'][i]['tracks'])):
            if album_play_count_json['data']['discs'][i]['tracks'][j]['name'].lower().rstrip() == track.lower().rstrip().encode('utf-8').decode('utf-8') or track.lower().rstrip().encode('utf-8').decode('utf-8') in album_play_count_json['data']['discs'][i]['tracks'][j]['name'].lower().rstrip():
                return album_play_count_json['data']['discs'][i]['tracks'][j]['playcount']

    return -3

def generate_owners():

    # check if province is free before updating

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    ranking_cursor = mydb.cursor(buffered=True)
    ranking_cursor.execute("TRUNCATE TABLE provinceOwners")
    ranking_cursor.execute("SELECT h.artist,l.province,sum(h.playCount) FROM `hits` AS h INNER JOIN locations AS l ON h.locationID = l.id WHERE h.locationID > 0 AND h.playCount > 0 GROUP BY artist,l.province ORDER BY sum(playCount) DESC")
    insert_cursor = mydb.cursor(buffered=True)

    owned_provinces = []

    for res_rank in ranking_cursor:
        sql = "INSERT INTO provinceOwners (province, owner) VALUES (%s, %s)"
        val = (res_rank[1],res_rank[0])
        log.info(f"Setting {res_rank[0]} owner of {res_rank[1]} with {res_rank[2]} playcount!")
        if not res_rank[1] in owned_provinces:
            insert_cursor.execute(sql,val)
            owned_provinces.append(res_rank[1])

    mydb.commit()

    return

def json_for_map():

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    map_cursor = mydb.cursor()
    map_cursor.execute("SELECT province,owner FROM provinceOwners")

    if not os.path.isfile('colors.json'):
        log.critical("Unable to find colors.json")
        return

    colors_json_fp = open('colors.json','r')
    saved_colors = json.load(colors_json_fp)

    final_colors = {}

    artists = []
    paths_array = []

    province_box = {}
    
    divId = 0
    used_colors = 0

    number_of_colors = 107
    color_palette = ["#"+''.join([random.choice('0123456789ABCDEF') for j in range(6)]) for i in range(number_of_colors)]

    for res_map in map_cursor:
        artist_tmp = res_map[1]
        artists.append(artist_tmp)
        if artist_tmp not in saved_colors:
            saved_colors['colors'].append({artist_tmp: color_palette[used_colors]})
            final_colors[artist_tmp] = color_palette[used_colors]
            used_colors += 1
        else:
            final_colors[artist_tmp] = saved_colors[artist_tmp]

    # Update JSON if we added new colors

    if used_colors > 0:
        colors_json_fp.close()
        colors_json_fp = open('colors.json', 'w')
        json.dump(saved_colors, colors_json_fp, indent = 2)


    for artist in artists:
        map_cursor = mydb.cursor()
        map_cursor.execute(f"SELECT province FROM provinceOwners WHERE owner = '{artist}'")
        for res_map in map_cursor:
            paths_array.append(res_map[0])

        city = {'div':f'#box{divId}', 'label':artist.title(), 'paths': paths_array}
        if artist in final_colors:
            color_TMP = final_colors[artist]
        else:
            log.info(f"NO COLOR FOR {artist}")
            exit()

        province_box[color_TMP] = city
        divId += 1
        paths_array = []

    root = {'groups':province_box}

    final_json = json.dumps(root)

    print(final_json)

    return final_json

def download_map(json_map):

    # Init Firefox/Selenium Object
    firefox_profile = webdriver.FirefoxProfile()
    firefox_options = webdriver.FirefoxOptions()
    firefox_options.add_argument('--headless')
    firefox_profile.set_preference('browser.download.folderList', 2) # Download in custom location
    firefox_profile.set_preference('browser.download.manager.showWhenStarting', False) # Don't show the download window
    firefox_profile.set_preference('browser.download.dir', os.getcwd()) # Download location
    firefox_profile.set_preference('browser.download.downloadDir', os.getcwd()) # Download location
    firefox_profile.set_preference('browser.download.defaultFolder', os.getcwd()) # Download location
    firefox_profile.set_preference('browser.helperApps.neverAsk.saveToDisk', 'image/png') # Download .png files without showing the download prompt

    browser = webdriver.Firefox(options=firefox_options, firefox_profile=firefox_profile)
    browser.get('https://mapchart.net/italy.html')

    element = browser.find_element_by_id('downup')
    browser.execute_script("arguments[0].click();", element) # HACK: Make downup clickable ignoring "<div class=loader> blocking it".

    condition = ec.visibility_of_element_located((By.ID, 'uploadData'))
    WebDriverWait(browser, 15).until(condition)
    browser.find_element_by_id('uploadData').send_keys(json_map)

    browser.find_element_by_id('upload').click()
    
    element = browser.find_element_by_id('convert')
    browser.execute_script("arguments[0].click();", element) # HACK: Make convert clickable ignoring "<div class=loader> blocking it".

    condition = ec.visibility_of_element_located((By.ID, 'download'))
    WebDriverWait(browser, 30).until(condition)

    # Remove old map before downloading the new one.

    if os.path.isfile('map.png'):
        os.remove('map.png')

    browser.find_element_by_id('download').click()
    browser.close()

    # Rename downloaded file

    for single_file in os.listdir():
        if '.png' in single_file:
            os.rename(single_file,'map.png')

    return


def update_score():

    ignore = False

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    # mydb_select is a connection handle only for the select statement to prevent the "Unread results found" error.
    mydb_select = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase']) 

    songslocations_cursor = mydb_select.cursor()
    songslocations_cursor.execute(f"SELECT a.artist_name,l.song_title,l.song_city FROM {config['indiemap_db']}.songslocations AS l LEFT JOIN {config['indiemap_db']}.artists AS a ON a.artist_id = l.song_artist_id")

    for songlocation in songslocations_cursor:
        artist = songlocation[0].rstrip()
        title = songlocation[1].rstrip()
        city = songlocation[2].rstrip()
        id = artist + "|" + title + "|" + city
        id = hashlib.md5(id.encode('utf-8')).hexdigest()

        location_ID = getlocation_ID(city)
        play_count = get_play_count(artist,title)

        existsCursor = mydb.cursor(buffered=True)
        existsCursor.execute("SELECT playCount FROM hits WHERE id = '" + id + "'")

        for res in existsCursor:
            # Already exists, update
            if play_count > res[0]:
                # Got more play_count (test)
                update_cursor = mydb.cursor(buffered=True)
                update_cursor.execute("UPDATE hits SET playCount = " + str(play_count) + " WHERE id = '" + id + "'")
                mydb.commit()
            elif res[0] > 0 and play_count < 0:
                # If I had a play_count but now I have not, warn me.
                log.warning(f"{artist} {title} was {str(res[0])} but now is {str(play_count)}. play_count WAS NOT UPDATED!")
                ignore = True

            log.info(f"Updated {title} by {artist}")
        if ignore:
            ignore = False
            continue


        sql = "INSERT INTO hits (id, artist, title, city, playCount, locationID) VALUES (%s, %s, %s, %s, %s,%s)"
        val = (id, artist, title, city, play_count, location_ID)
        insert_cursor = mydb.cursor()
        
        insert_cursor.execute(sql, val)
        mydb.commit()
        
        log.info(f"Added {title} by {artist}")

    mydb.close()

    return

if __name__ == '__main__':
    main()