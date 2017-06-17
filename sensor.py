import json
import sys
import time
import datetime

import spidev
import os

import Adafruit_DHT
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Type of sensor, can be Adafruit_DHT.DHT11, Adafruit_DHT.DHT22, or Adafruit_DHT.AM2302.
DHT_TYPE = Adafruit_DHT.DHT11

# Example of sensor connected to Raspberry Pi pin 23
DHT_PIN  = 4
# Example of sensor connected to Beaglebone Black pin P8_11
#DHT_PIN  = 'P8_11'

# open(bus, device) : open(X,Y) will open /dev/spidev-X.Y
spi = spidev.SpiDev()
spi.open(0,0)
 
#read SPI data from MCP3008, Channel must be an integer 0-7
def ReadADC(ch):
    if((ch > 7) or (ch < 0)):
        return -1
    adc = spi.xfer2([1, (8 + ch) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data
 
#Calculate soil moisture from MTARDMO
def ReadVolts(data, deci):
    volts = (data * 3.3) / float(1023)
    volts = round(volts, deci)
    return volts
 
#Define sensor channels
light_ch = 0
soilmoi_ch = 1

GDOCS_OAUTH_JSON       = 'yourJsonFile.json'

# Google Docs spreadsheet name.
GDOCS_SPREADSHEET_NAME = 'raspberry_pi_sensor'

# How long to wait (in seconds) between measurements.
FREQUENCY_SECONDS      = 1800


def login_open_sheet(oauth_key_file, spreadsheet):
    """Connect to Google Docs spreadsheet and return the first worksheet."""
    try:
        scope =  ['https://spreadsheets.google.com/feeds']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(oauth_key_file, scope)
        gc = gspread.authorize(credentials)
        worksheet = gc.open(spreadsheet).sheet1
        return worksheet
    except Exception as ex:
        print('Unable to login and get spreadsheet.  Check OAuth credentials, spreadsheet name, and make sure spreadsheet is shared to the client_email address in the OAuth .json file!')
        print('Google sheet login failed with error:', ex)
        sys.exit(1)


print('Logging sensor measurements to {0} every {1} seconds.'.format(GDOCS_SPREADSHEET_NAME, FREQUENCY_SECONDS))
print('Press Ctrl-C to quit.')
worksheet = None
while True:
    # Login if necessary.
    if worksheet is None:
        worksheet = login_open_sheet(GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME)

    # Attempt to get sensor reading.
    humidity, temp = Adafruit_DHT.read(DHT_TYPE, DHT_PIN)
    
     #Read the soil moisture sensor data
    soilmoi_data = ReadADC(soilmoi_ch)
    soilmoi_volts = ReadVolts(soilmoi_data, 2)
    
    #Read the light sensor data
    light_data = ReadADC(light_ch)
    light_volts = ReadVolts(light_data, 2)

    # Skip to the next reading if a valid measurement couldn't be taken.
    # This might happen if the CPU is under a lot of load and the sensor
    # can't be reliably read (timing is critical to read the sensor).
    if humidity is None or temp is None:
        time.sleep(2)
        continue

    print('Temperature: {0:0.1f} C'.format(temp))
    print('Humidity:    {0:0.1f} %'.format(humidity))
    print "Soil moisture : ", soilmoi_data, " (", soilmoi_volts,"V),"
    print "Light : ", light_data, " (", light_volts,"V)"

    # Append the data in the spreadsheet, including a timestamp
    try:
        worksheet.append_row((datetime.datetime.now(), temp, humidity, light_data, soilmoi_data))
    except:
        # Error appending data, most likely because credentials are stale.
        # Null out the worksheet so a login is performed at the top of the loop.
        print('Append error, logging in again')
        worksheet = None
        time.sleep(FREQUENCY_SECONDS)
        continue

    # Wait 30 seconds before continuing
    print('Wrote a row to {0}'.format(GDOCS_SPREADSHEET_NAME))
    time.sleep(FREQUENCY_SECONDS)
