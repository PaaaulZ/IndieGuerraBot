import requests
import json
import os
import mysql.connector
import hashlib

def loadConfig():

    if not os.path.exists('config.json'):
        print("Cannot find config.json")
        exit()

    fConfig = open('config.json','r')

    return json.load(fConfig)

config = loadConfig()

def getLocationID(cityName):

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    mycursor = mydb.cursor()
    mycursor.execute("SELECT id FROM locations WHERE city = '" + cityName + "'")

    locationID = -1
    for res in mycursor:
        locationID = res[0]
        break
    
    mydb.close()
    
    return locationID

def getSpotifyAlbumID(artist,track,next = ''):

    if next is None or next == '':
        url = "https://api.spotify.com/v1/search?q=" + track.lower().rstrip() + " " + artist + "&type=track&limit=50"
    else:
        url = next
    
    r = requests.get(url, headers={"Accept":"application/json","Content-Type":"application/json","Authorization":"Bearer " + config['spotifyApiKey']})
    if r.status_code != 200:
        print("Unable to search track from Spotify ",r.status_code)
        exit()

    tracksJson = json.loads(r.text)

    for i in range(len(tracksJson['tracks']['items'])):       

        # Check if artist present
        for j in range(len(tracksJson['tracks']['items'][i]['artists'])):
            if tracksJson['tracks']['items'][i]['artists'][j]['name'].lower().rstrip() == artist.lower().rstrip().encode('utf-8').decode('utf-8') or artist.lower().rstrip().encode('utf-8').decode('utf-8') in tracksJson['tracks']['items'][i]['name'] or artist.lower().rstrip().encode('utf-8').decode('utf-8') in tracksJson['tracks']['items'][i]['artists'][j]['name'].lower().rstrip():
                return tracksJson['tracks']['items'][i]['album']['id']

        #if tracksJson['tracks']['next'] != '':
        #    getSpotifyAlbumID(artist,track,tracksJson['tracks']['next'])

    return "NO_MATCH"

def getPlayCount(artist,track):

    spotifyAlbumID = getSpotifyAlbumID(artist,track)

    if spotifyAlbumID == 'NO_MATCH':
        print("NO ALBUM ID FOR " + track + " BY " + artist)
        return -1

    r = requests.get("https://t4ils.dev/api/beta/albumPlayCount?albumid=" + spotifyAlbumID)
    albumPlayCountJson = json.loads(r.text)

    if not albumPlayCountJson['success']:
        print("Cannot get album playcount for " + artist + "/" + track + "/" + spotifyAlbumID)
        return -2
    
    for i in range(len(albumPlayCountJson['data'])):
        if albumPlayCountJson['data'][i]['name'].lower().rstrip() == track.lower().rstrip().encode('utf-8').decode('utf-8') or track.lower().rstrip().encode('utf-8').decode('utf-8') in albumPlayCountJson['data'][i]['name'].lower().rstrip():
            return albumPlayCountJson['data'][i]['playcount']

    return -3

def generateOwners():

    # check if province is free before updating

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    rankingCursor = mydb.cursor(buffered=True)
    rankingCursor.execute("TRUNCATE TABLE provinceOwners")
    rankingCursor.execute("SELECT artist,l.province,sum(playCount) FROM `hits` AS h INNER JOIN locations AS l ON h.locationID = l.id WHERE locationID > 0 GROUP BY artist,l.province ORDER BY sum(playCount) DESC")
    insertCursor = mydb.cursor(buffered=True)

    ownedProvinces = []

    for resRank in rankingCursor:
        sql = "INSERT INTO provinceOwners (province, owner) VALUES (%s, %s)"
        val = (resRank[1],resRank[0])
        if not resRank[1] in ownedProvinces:
            insertCursor.execute(sql,val)
            ownedProvinces.append(resRank[1])

    mydb.commit()

    return

def drawMap():

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])
    mapCursor = mydb.cursor()
    mapCursor.execute("SELECT province,owner FROM provinceOwners")

    fixedColors = {'Brunori Sas':'#238b45','Calcutta':'#88419d','Carl Brave':'#4ed3b3','CLAVDIO':'#ef6548','Coez':'#3690c0','Eugenio in via di gioia':'#41ab5d','Ex-Otago':'#fc4e2a','Frah Quintale':'#800026','Gazzelle':'#737373','I cani':'#d9f0d3','La Municipàl':'#ffff33','Liberato':'#8c510a','Motta':'#7171c6','Pinguini Tattici Nucleari':'#542788','Scarda':'#000000','The Zen Circus':'#e31c2c','Thegiornalisti':'#fdb462','Tommy toxxic':'#ffffbf'}

    artists = []
    pathsArray = []

    provinceBox = {}
    
    divId = 0
    for resMap in mapCursor:
        artists.append(resMap[1])

    for artist in artists:
        mapCursor = mydb.cursor()
        mapCursor.execute(f"SELECT province FROM provinceOwners WHERE owner = '{artist}'")
        for resMap in mapCursor:
            pathsArray.append(resMap[0])

        city = {'div':f'#box{divId}', 'label':artist, 'paths': pathsArray}
        if artist in fixedColors:
            colorTMP = fixedColors[artist]
        else:
            print("NO COLOR FOR {artist}")
            exit()

        provinceBox[colorTMP] = city
        divId += 1
        pathsArray = []

    root = {'groups':provinceBox}
  
    jsonForMap = open('json4map.json','w')
    json.dump(root,jsonForMap)


    return


def updateScore():

    ignore = False

    if not os.path.exists('found4map.json'):
        print("Cannot find found4map.json")
        exit()

    fIN = open('found4map.json',mode="r", encoding="utf-8")

    jsonMap = json.load(fIN)

    mydb = mysql.connector.connect(host=config['dbhost'],user=config['dbuser'],passwd=config['dbpass'],database=config['dbase'])

    for fakeIndex in jsonMap:
        artist = jsonMap[str(fakeIndex)][0]['artist'].rstrip()
        title = jsonMap[str(fakeIndex)][0]['title'].rstrip()
        city = jsonMap[str(fakeIndex)][0]['city'].rstrip()
        id = artist + "|" + title + "|" + city
        id = hashlib.md5(id.encode('utf-8')).hexdigest()
        locationID = getLocationID(city)

        playCount = getPlayCount(artist,title)

        existsCursor = mydb.cursor()
        existsCursor.execute("SELECT playCount FROM hits WHERE id = '" + id + "'")

        for res in existsCursor:
            # Already exists, update
            if playCount > res[0]:
                # Got more playCount (test)
                updateCursor = mydb.cursor()
                updateCursor.execute("UPDATE hits SET playCount = " + str(playCount) + " WHERE id = '" + id + "'")
                mydb.commit()
            elif res[0] > 0 and playCount < 0:
                # If I had a playCount but now I have not warn me.
                print("WARNING: " + artist + " - " + title + " was " + str(res[0]) + " but now is " + str(playCount))

            ignore = True

            print("\t Updated " + title + " by " + artist)
        if ignore:
            continue


        sql = "INSERT INTO hits (id, artist, title, city, playCount, locationID) VALUES (%s, %s, %s, %s, %s,%s)"
        val = (id, artist, title, city, playCount, locationID)
        existsCursor = mydb.cursor()
        
        existsCursor.execute(sql, val)
        mydb.commit()
        
        print("\t Added " + title + " by " + artist)

        mydb.close()

    return


#updateScore()
#generateOwners()
drawMap()