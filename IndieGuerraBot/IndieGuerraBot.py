import requests
import json
import os
import mysql.connector
import hashlib
import logging
import random
import ftplib
from time import sleep
from datetime import datetime
from shutil import copyfile
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
    ret_config = json.load(f_config)
    f_config.close()

    return ret_config

config = load_config()
fh = logging.FileHandler('indieguerrabot.log')
log = logging.getLogger('IndieGuerraBot')

def main():

    logging.basicConfig(format='%(asctime)s - [%(levelname)s]: %(message)s')
    if config['logLevel'] == '' or config['logLevel'] == 0:
        log.setLevel(logging.ERROR)
    elif config['logLevel'] == 1:
        log.setLevel(logging.WARNING)
    else:
        log.setLevel(logging.DEBUG)

    log.addHandler(fh)

    update_score()
    backup_previous_owners()
    generate_owners()
    result_json = json_for_map()
    download_map(result_json)
    calculate_differences()
    upload_final_files()
    log.info("All done!")

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

def get_spotify_album_ID(artist,track):

    url = f"https://api.spotify.com/v1/search?q={track.lower().rstrip()} {artist}&type=track&limit=50"

    r = requests.get(url, headers={"Accept":"application/json","Content-Type":"application/json","Authorization":"Bearer " + config['spotifyApiKey']})
    if r.status_code == 401:
        raise Exception("Spotify error 401, expired API key?")
    elif r.status_code != 200:
        log.warning(f"Unable to search {artist} - {track} from Spotify {r.status_code}")
        return "NO_MATCH"

    tracks_json = json.loads(r.text)

    for i in range(len(tracks_json['tracks']['items'])):

        # Check if artist present
        for j in range(len(tracks_json['tracks']['items'][i]['artists'])):
            if tracks_json['tracks']['items'][i]['artists'][j]['name'].lower().rstrip() == artist.lower().rstrip().encode('utf-8').decode('utf-8') or artist.lower().rstrip().encode('utf-8').decode('utf-8') in tracks_json['tracks']['items'][i]['name'] or artist.lower().rstrip().encode('utf-8').decode('utf-8') in tracks_json['tracks']['items'][i]['artists'][j]['name'].lower().rstrip():
                return tracks_json['tracks']['items'][i]['album']['id']

    return "NO_MATCH"

def get_play_count(artist,track):

    spotify_album_ID = get_spotify_album_ID(artist,track)

    if spotify_album_ID == 'NO_MATCH':
        # Cannot find album id, return code = -1
        log.info(f"No album id for {track} by {artist}, cannot get playcount")
        return -1

    r = requests.get(f"https://api.t4ils.dev/albumPlayCount?albumid={spotify_album_ID}")
    if r.status_code != 200:
        log.warning(f"Unable to get playcount for {track} by {artist} ({r.status_code})")
        return -2

    album_play_count_json = json.loads(r.text)

    if not album_play_count_json['success']:
        # Cannot get playcount, return code = -2
        log.warning(f"Cannot get album play_count for {track} by {artist} on albumid {spotify_album_ID}")
        return -2

    for i in range(len(album_play_count_json['data']['discs'])):
        for j in range(len(album_play_count_json['data']['discs'][i]['tracks'])):
            if album_play_count_json['data']['discs'][i]['tracks'][j]['name'].lower().rstrip() == track.lower().rstrip().encode('utf-8').decode('utf-8') or track.lower().rstrip().encode('utf-8').decode('utf-8') in album_play_count_json['data']['discs'][i]['tracks'][j]['name'].lower().rstrip():
                return album_play_count_json['data']['discs'][i]['tracks'][j]['playcount']

    # Other error, return code -3 (ex: found album, success api call but can't match artist/title in album)
    return -3

def backup_previous_owners():
    
    # Backup previous owners to generate differences

    log.info("Backing up previous owners")
    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    prev_owners_cursor = mydb.cursor(buffered=True)
    prev_owners_cursor.execute("TRUNCATE TABLE prevProvinceOwners")
    log.debug("Deleted previous owners")
    prev_owners_cursor.execute("INSERT INTO prevProvinceOwners SELECT * FROM provinceOwners")
    mydb.commit()
    log.info("Backed up previous ownwers")

    return

def calculate_differences():
    # TODO: This should be done DB side and not here, we need a better table structure.
    # WARNING: differences.log will be overwritten, the file always stores only the LAST run.

    differences_fp = open('differences.log','w')
        
    log.info("Calculating differences in owners")
    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    log.debug("Getting provinces")
    cursor = mydb.cursor(buffered=True)
    cursor.execute("SELECT DISTINCT province FROM locations GROUP BY province")

    provinces = []
    for res_province in cursor:
        provinces.append(res_province[0])
    log.debug(f"Got {len(provinces)} provinces")

    log.debug("Getting current owners")

    current_owners = {}
    cursor.execute("SELECT * FROM provinceOwners")
    for res_owner in cursor:
        current_owners[res_owner[0]] = res_owner[1]

    log.debug(f"Got {len(current_owners)} current owners")
    cursor.execute("SELECT * FROM prevProvinceOwners")
    for res_prev_owner in cursor:
        # For every previous owner
        province_tmp = res_prev_owner[0]
        previous_owner_tmp = res_prev_owner[1]
        if province_tmp in current_owners:
            current_owner_tmp = current_owners[province_tmp]
            # Found current owner for this previous owner
            if previous_owner_tmp != current_owner_tmp:
                # Is different?
                log.info(f"{current_owners[province_tmp].title()} got {province_tmp.title()} from {previous_owner_tmp.title()}")
                differences_fp.write(f"{current_owners[province_tmp].title()} got {province_tmp.title()} from {previous_owner_tmp.title()}\n")

    mydb.commit()
    differences_fp.close()

    return

def generate_owners():

    log.info("Generating province owners")

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    ranking_cursor = mydb.cursor(buffered=True)
    ranking_cursor.execute("TRUNCATE TABLE provinceOwners")
    ranking_cursor.execute("SELECT h.artist,l.province,sum(h.playCount) FROM `hits` AS h INNER JOIN locations AS l ON h.locationID = l.id WHERE h.locationID > 0 AND h.playCount > 0 GROUP BY artist,l.province ORDER BY sum(playCount) DESC")
    insert_cursor = mydb.cursor(buffered=True)

    owned_provinces = []

    for res_rank in ranking_cursor:
        sql = "INSERT INTO provinceOwners (province, owner) VALUES (%s, %s)"
        val = (res_rank[1],res_rank[0])
        log.info(f"Setting {res_rank[0]} owner of {res_rank[1]} with {res_rank[2]} playcount")
        if not res_rank[1] in owned_provinces:
            insert_cursor.execute(sql,val)
            owned_provinces.append(res_rank[1])

    mydb.commit()

    log.info("Province owners generated")

    return

def json_for_map():

    log.info("Generating JSON for map download")

    already_done_artists = []

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    map_cursor = mydb.cursor()
    map_cursor.execute("SELECT province,owner FROM provinceOwners")

    if not os.path.isfile('colors.json'):
        log.critical("Unable to find colors.json, exiting.")
        raise Exception("Unable to find colors.json, exiting.")

    # Opening colors.json to fetch pre-assigned colors.
    colors_json_fp = open('colors.json','r')
    saved_colors = json.load(colors_json_fp)
    saved_colors_obj = {}

    # Saving existing colors to check for duplicates
    existing_colors = []

    for artist in saved_colors:
        existing_colors.append(saved_colors[artist])

    final_colors = {}
    province_box = {}

    artists = []
    paths_array = []

    divId = 0
    used_colors = 0

    # Worst case we need a color for every province so we generate a palette of 107 random colors
    number_of_colors = 107
    color_palette = ["#"+''.join([random.choice('0123456789ABCDEF') for j in range(6)]) for i in range(number_of_colors)]

    for res_map in map_cursor:
        # Get a color for every province owner (pre-assigned or new random color)
        artist_tmp = res_map[1]
        artists.append(artist_tmp)
        if artist_tmp in already_done_artists:
            log.info(f"Skipping {artist_tmp}, already assigned a color")
            continue

        already_done_artists.append(artist_tmp)
        if artist_tmp not in saved_colors:
            # New random color
            log.debug(f"{artist_tmp} has no color pre-assigned, new color will be {color_palette[used_colors]}")
            while (color_palette[used_colors] in existing_colors):
                # If new random color is already used try a new one
                log.info(f"{color_palette[used_colors]} already used, generating new color")
                used_colors += 1
                saved_colors_obj[artist_tmp] = color_palette[used_colors]
                final_colors[artist_tmp] = color_palette[used_colors]
            else:
                # If not already existing just take one
                saved_colors_obj[artist_tmp] = color_palette[used_colors]
                final_colors[artist_tmp] = color_palette[used_colors]
                used_colors += 1
        else:
            # Pre-assigned color
            log.debug(f"{artist_tmp} has pre-assigned color {saved_colors[artist_tmp]}")
            final_colors[artist_tmp] = saved_colors[artist_tmp]
            
    saved_colors.update(saved_colors_obj)

    # Update JSON if we added new colors

    if used_colors > 0:
        # Found new colors, update colors.json
        colors_json_fp.close()
        colors_json_fp = open('colors.json', 'w')
        json.dump(saved_colors, colors_json_fp, indent = 2)
        colors_json_fp.close()
        log.debug(f"Added {used_colors} new colors")


    for artist in artists:
        # Get province for every owner
        # TODO: Do we really need both this and the upper query?

        map_cursor = mydb.cursor()
        map_cursor.execute(f"SELECT province FROM provinceOwners WHERE owner = '{artist}'")
        for res_map in map_cursor:
            paths_array.append(res_map[0])

        city = {'div':f'#box{divId}', 'label':artist.title(), 'paths': paths_array}

        assert artist in final_colors, f"No color for {artist}???"

        color_TMP = final_colors[artist]

        province_box[color_TMP] = city
        divId += 1
        paths_array = []

    root = {'groups':province_box}

    final_json = json.dumps(root)

    log.info("JSON generated.")

    return final_json


def download_map(json_map):

    log.info("Starting map download")

    # Init Chrome/Selenium Object
    chrome_options = webdriver.ChromeOptions()

    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--verbose')
    chrome_options.add_experimental_option("prefs", {
            "download.default_directory": os.getcwd(),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing_for_trusted_sources_enabled": False,
            "safebrowsing.enabled": False
    })
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')

    browser = webdriver.Chrome(options=chrome_options)
    browser.get('https://mapchart.net/italy.html')

    element = browser.find_element_by_id('downup')
    browser.execute_script("arguments[0].click();", element) # HACK: Make downup clickable ignoring "<div class=loader> blocking it".

    condition = ec.visibility_of_element_located((By.ID, 'uploadData'))
    WebDriverWait(browser, 15).until(condition)
    uploadDataTextArea = browser.find_element_by_id('uploadData')
    browser.execute_script(f"arguments[0].value = '{json_map}'", uploadDataTextArea) # Changing the height of the final image

    browser.find_element_by_id('upload').click()

    element = browser.find_element_by_id('canvas1')
    browser.execute_script(f"arguments[0].width = {config['mapImageWidth']}", element) # Changing the height of the final image
    browser.execute_script(f"arguments[0].height = {config['mapImageHeight']}", element) # Changing the height of the final image

    if config['hideMapColorLegend']:
        # Hide default legend if you want to draw your own
        element = browser.find_element_by_id('disableLegend')
        browser.execute_script("arguments[0].click();", element) # HACK: Make disableLegend clickable ignoring "<div class=modal-backdrop fade in> blocking it".

    element = browser.find_element_by_id('convert')
    browser.execute_script("arguments[0].click();", element) # HACK: Make convert clickable ignoring "<div class=loader> blocking it".

    condition = ec.visibility_of_element_located((By.ID, 'download'))
    WebDriverWait(browser, 30).until(condition)

    # Remove old map before downloading the new one.

    if os.path.isfile('map.png'):
        os.remove('map.png')

    browser.find_element_by_id('download').click()

    # Arbitrary wait because Chrome loves closing before finishing the download...
    log.debug("Sleeping 5 seconds to allow Chrome to finish the download")
    sleep(5)
    browser.close()

    # Rename downloaded file

    for single_file in os.listdir():
        if '.png' in single_file:
            os.rename(single_file,'map.png')

    if os.path.isfile('map.png'):
        log.info('Map saved as map.png')
    else:
        log.error('Cannot find map.png, map not downloaded?')

    return

def upload_final_files():

    if config['uploadMethod'] == 'ftp':
        log.info(f"Starting FTP upload on {config['ftpHost']}")
        session = ftplib.FTP(config['ftpHost'],config['ftpUsername'],config['ftpPassword'])
        # Need to know how many runs are present
        session.cwd(config['ftpFolder'])
        # Need to ignore index.htm
        next_run_id = len(session.nlst()) - 1
        # Create run folder
        session.mkd(str(next_run_id))
        runFolder = f"{config['ftpFolder']}/{str(next_run_id)}"
        session.cwd(runFolder)
        log.debug(f"Run folder is {runFolder}")
        try:
            # Upload image
            log.debug('Uploading map.png')
            map_fp = open('map.png','rb')
            session.storbinary('STOR map.png', map_fp)
            map_fp.close()
            # Upload differences
            log.debug('Uploading differences.log')
            differences_fp = open('differences.log','rb')
            session.storbinary('STOR differences.log', differences_fp)
            differences_fp.close()
            log.info(f"Done uploading files, final folder is {runFolder}")
        except:
            log.critical('Error uploading files.')
        session.quit()
    elif config['uploadMethod'] == 'copy':
        log.info(f"Starting file copy to {config['copyFolder']}")
        # Need to ignore index.htm
        next_run_id = len(os.listdir(config['copyFolder'])) - 1
        # Create run folder
        run_folder = f"{config['copyFolder']}/{next_run_id}"
        os.mkdir(run_folder)
        # Copy map.png
        log.debug('Copying map.png')
        copyfile('map.png',f"{run_folder}/map.png")
        # Copy differences.log
        log.debug('Copying differences.log')
        copyfile('differences.log',f"{run_folder}/differences.log")
        log.info(f"Done copying, final folder is {run_folder}")
    else:
        log.critical(f"Upload method {config['uploadMethod']} is not valid, aborting!")
        raise Exception(f"Upload method {config['uploadMethod']} is not valid, aborting!")

    return

def update_score():

    log.info("Updating playcounts")

    ignore = False

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    # HACK: mydb_select is a connection handle only for the select statement to prevent the "Unread results found" error.
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
                log.info(f"Updated {title} by {artist}")
                continue
            elif res[0] > 0 and play_count < 0:
                # If I had a play_count but now I have not, warn me.
                log.warning(f"{artist} {title} was {str(res[0])} but now is {str(play_count)}. PLAYCOUNT WAS NOT UPDATED!")
                continue

        if ignore:
            ignore = False
            continue

        # Add new line if a playcount is not present
        sql = "INSERT INTO hits (id, artist, title, city, playCount, locationID) VALUES (%s, %s, %s, %s, %s,%s)"
        val = (id, artist, title, city, play_count, location_ID)
        insert_cursor = mydb.cursor()

        insert_cursor.execute(sql, val)
        mydb.commit()

        log.info(f"Added {title} by {artist}")

    mydb.close()

    log.info("Playcounts updated")

    return

if __name__ == '__main__':
    main()
