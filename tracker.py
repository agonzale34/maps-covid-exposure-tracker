import datetime as dt
import http.cookies
import json
from xml.dom import minidom

import dateutil.parser as dp
import requests
import requests.cookies
from dateutil import tz

MAPS_TODAY_URL = 'https://www.google.ca/maps/timeline?pli=1&pb=!1m2!1m1!1s{}-{}-{}'
BASE_URL = 'https://www.google.ca/maps/timeline/kml?authuser=0&pb=!1m8!1m3!1i{0}!2i{1}!3i{2}!2m3!1i{0}!2i{1}!3i{2}'
TIMELINE_FILE_TEMPLATE = 'timelines/{}-{}-{}.kml'
EXPOSURE_FILE_TEMPLATE = 'exposures/{}.json'


def get_map_url(year, month, day):
    return BASE_URL.format(year, month - 1, day)


def print_line_separator():
    print('-----------------------------------------------------------------------------------')


def download_maps_timeline(year, month, day, cookie_jar):
    r = requests.get(get_map_url(year, month, day), cookies=cookie_jar)
    if r.status_code == 200:
        file_name = TIMELINE_FILE_TEMPLATE.format(year, month, day)
        with open(file_name, 'w') as f:
            f.write(r.text)
            print("File", file_name, "stored successfully")


def process_exposure_day(date, exposures):
    exposure_day = next((item for item in exposures['exposures'] if item['date'] == date.strftime('%Y-%m-%d')), None)
    possible_exposures = []
    if exposure_day is not None:
        default_date_time = dt.datetime(date.year, date.month, date.day, tzinfo=tz.gettz(exposures['timezone']))
        locations = exposure_day['locations']
        # open the kml file for this date
        timeline = minidom.parse(TIMELINE_FILE_TEMPLATE.format(date.year, date.month, date.day))
        places = timeline.getElementsByTagName('Placemark')
        # process places that are not driving/moving/running
        for place in places:
            point = place.getElementsByTagName('Point')
            if point:
                place_name = place.getElementsByTagName('name')[0].firstChild.data
                place_address = place.getElementsByTagName('address')[0].firstChild.data
                for location in locations:
                    if location['address'].lower() == place_address.lower():
                        # the address match, now we check the time frame:
                        time_span = place.getElementsByTagName('TimeSpan')[0]
                        begin = dp.parse(location['begin'], default=default_date_time)
                        end = dp.parse(location['end'], default=default_date_time)
                        begin_place = dp.parse(time_span.getElementsByTagName('begin')[0].firstChild.data)
                        if begin <= begin_place <= end:
                            possible_exposures.append({
                                "name": place_name,
                                "address": place_address,
                                "start_time": begin_place
                            })

    return possible_exposures


def run():
    print_line_separator()
    print('Welcome to Maps COVID exposure tracker')
    print_line_separator()
    days_past = input('How many days in that past you would like to check[14]: ')
    if days_past == '':
        days_past = 14
    else:
        days_past = int(days_past)

    init_date = dt.datetime.today() - dt.timedelta(days=days_past)
    final_date = dt.datetime.today()
    print('Interval to check:', init_date.strftime('%Y-%m-%d'), final_date.strftime('%Y-%m-%d'))

    should_get_data = input('Would do you like to get the timeline data [Y/n]: ')
    if should_get_data.lower() == 'y':
        print('Get google cookie by downloading the current kml file')
        print(MAPS_TODAY_URL.format(final_date.year, final_date.month, final_date.day))
        cookie = input('Please insert the cookie: ')

        simple_cookie = http.cookies.SimpleCookie(cookie)
        cookie_jar = requests.cookies.RequestsCookieJar()
        cookie_jar.update(simple_cookie)

        for i in range(days_past):
            date_to_get = init_date + dt.timedelta(days=i)
            download_maps_timeline(date_to_get.year, date_to_get.month, date_to_get.day, cookie_jar)
        print('All days downloaded')

    file_name = input('Please insert the exposure filename [nova-scotia]: ')
    if file_name == '':
        file_name = 'nova-scotia'
    exposure_file_path = EXPOSURE_FILE_TEMPLATE.format(file_name)

    print_line_separator()
    print('Checking all the timelines against the database:', exposure_file_path)
    # open the exposures file
    with open(exposure_file_path, 'r') as read_file:
        exposures_data = json.load(read_file)
        all_possible_exposures = []
        # Iterate the timelines and validate against the exposures
        for i in range(days_past):
            date_to_check = init_date + dt.timedelta(days=i)
            day_possible_exposures = process_exposure_day(date_to_check, exposures_data)
            all_possible_exposures.extend(day_possible_exposures)

        print_line_separator()
        print('All days has been validated!')
        print_line_separator()

        if len(all_possible_exposures) > 0:
            print('ALERT: possible exposures found at:')
            for p_expo in all_possible_exposures:
                date_str = p_expo['start_time'].astimezone(tz.tzlocal()).strftime('%Y-%m-%d %H:%M')
                print('*', p_expo['name'], '- Time:', date_str)
        else:
            print('No possible exposure found at this time!')
