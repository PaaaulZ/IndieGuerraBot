# IndieGuerraBot
## Italian Indie artists love using city names in lyrics. What if this was a war, who is currently owning each province?

### What is this? / How does this work?

The goal for this project is to make italian indie artists "fight" for a province.
City names found in Italian indie songs lyrics get placed [on a map](http://paaaulz.altervista.org/indiemap/), the song with most playcount on Spotify wins and gets the province.
Every month the process starts all over again and hopefully some new song comes out and claims a province.

**This project relys on [IndieMap](https://github.com/PaaaulZ/IndieMap) for data**

### REQUIREMENTS

* A working and populated [IndieMap](https://github.com/PaaaulZ/IndieMap) database.
* A Spotify API key.
* [Google Chrome](https://www.google.com/intl/it_it/chrome/)
* [Chrome Driver](https://chromedriver.chromium.org/)
* Python libraries that you can import by using **pip3 install -r requirements.txt**


### INSTRUCTIONS

* Create your database by importing the attached indieguerrabot.sql.
* Edit config.json.empty with your settings and rename it to config.json.
* Place the previously downloaded chromedriver binary (chromedriver.exe on Windows) in the same folder of IndieGuerraBot.py.
* Rename colors.json.empty to colors.json
* Copy the contents of the **_website** folder on your website.
* Launch IndieGuerraBot.py.

### THANKS TO:

* [t4ils](https://t4ils.dev/) - evilarceus on [GitHub](https://github.com/evilarceus) for [sp-playcount-librespot](https://github.com/evilarceus/sp-playcount-librespot) and for hosting the public API.
* [MapChart](https://mapchart.net/) for providing an easy way to color and tag Italian provinces.
