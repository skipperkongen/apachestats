# apachestats
A small Python program to analyse Apache log files

Dependencies:

- Python 3

## How to use

First, [download](https://dev.maxmind.com/geoip/geoip2/geolite2/) a free maxmind city database (GeoLite2-City.mmdb) and store it somewhere.

Second, download some log files from your Apache web server. The files must be in "combined" format.

Finally, call the apachestats script like this:

```bash
python3 apachestats.py -w example.com -k 5 -m PATH/TO/GeoLite2-City.mmdb PATH/TO/logs/*.log
```

The script will print statistics like:

- approximate number of unique daily visitors
- top referers
- top locations (country and city)
- busiest hours
