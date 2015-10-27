# Automatically fetches menus for today, grades predefined cafes and based on
# additional information (weather, cafe of choice yesterday) gives recommendations
# where to go for lunch.
# If there are problems with encoding set Python encoding correctly by executing:
# set PYTHONIOENCODING=utf-8

from chief_lunch_officer import ChiefLunchOfficer, WeatherOpinion, FoodTaste
from constants import TEMPERATURE, PRECIPITATION_CHANCE, PRECIPITATION_AMOUNT, WIND
from constants import DAYBREAK, SODEXO_TERRA
from preferences import FOOD_PREFERENCES
from cafes import CAFES
from decorators import get_ignore_errors_decorator

from pathlib import Path
from datetime import date, datetime, timedelta
from copy import deepcopy
import urllib.request
import json
import re

EmptyMenuOnError = get_ignore_errors_decorator(default_value='No menu. Data feed format for the cafe changed?')


DAYBREAK_URL = 'http://www.compass-group.fi/Ravintolat/Espoo/Ravintola-Quartetto/Lounaslista/'
#SODEXO_TERRA_URL = 'http://www.sodexo.fi/ruokalistat/output/daily_json/546/%s/fi'
SODEXO_TERRA_URL = 'http://www.sodexo.fi/carte/load/html/546/%s/day'
YLE_WEATHER_FORECAST_URL = 'http://yle.fi/saa/resources/ajax/saa-api/hourly-forecast.action?id=642554'
#SODEXO_ACQUA_URL = 'http://www.sodexo.fi/carte/load/html/30/%s/day'
#SODEXO_EXPLORER_URL = 'http://www.sodexo.fi/carte/load/html/31/%s/day'

def make_readable(content_with_html_tags, insert_new_lines=True, collapse_whitespace=False):
    content_with_html_tags = re.sub('<br.*?>', '\n' if insert_new_lines else '', content_with_html_tags)
    content_with_html_tags = re.sub('<.*?>', '', content_with_html_tags)
    content_with_html_tags = re.sub('[ \t]+', ' ', content_with_html_tags)
    content_with_html_tags = re.sub('\n+', '\n', content_with_html_tags)
    if collapse_whitespace:
        content_with_html_tags = re.sub('\s+', ' ', content_with_html_tags)
        content_with_html_tags = re.sub("(.{80})", "\\1\n", content_with_html_tags, 0, re.DOTALL)
    content_with_html_tags = content_with_html_tags.replace('&amp;', '&').replace('&nbsp;', '')
    return content_with_html_tags.encode('ascii', 'ignore').decode('ascii')

def get(url):
    response = urllib.request.urlopen(url)
    charset = response.headers.get_content_charset() if response.headers.get_content_charset() is not None else 'utf-8'
    return response.read().decode(charset)

def get_and_find_all(url, regex):
    html = get(url)
    return re.findall(regex, html, re.MULTILINE | re.DOTALL)

def find_menu(url, date, regex, index=0):
    weekday = date.weekday()
    if (weekday > 4): #Saturday or Sunday
        return 'Weekend: no menu'
    found = get_and_find_all(url, regex)
    if (len(found) == 0):
        return 'No menu'
    else:
        return found[index]

@EmptyMenuOnError
def get_sodexo_terra_menu(date):
    menu_url = SODEXO_TERRA_URL % (date.strftime('%Y-%m-%d'))
    print(menu_url)
    menu = find_menu(menu_url, date, '(.*)')
    menu = json.loads(menu)['foods']
    return menu

@EmptyMenuOnError
def get_daybreak_menu(date):
    weekday = date.weekday()
    start = date.today().strftime("%A")
    end = (date.today() + timedelta(1)).strftime("%A")
    return find_menu(DAYBREAK_URL, date, r'%s(.*?)<strong>.*%s' % (start, end))

def get_todays_weather():
    weather_response = get(YLE_WEATHER_FORECAST_URL)
    forecast = json.loads(weather_response)['weatherInfos'][0]
    return {
        TEMPERATURE: forecast['temperature'],
        PRECIPITATION_CHANCE: forecast['probabilityPrecipitation'],
        PRECIPITATION_AMOUNT: forecast['precipitation1h'],
        WIND: forecast['windSpeedMs']
    }

def week_number(date):
    return date.isocalendar()[1]

def parse_date(date_str):
    return datetime.strptime(date_str, '%d.%m.%Y')

def get_current_week_history(today):
    history_path = Path('history.json')
    if not history_path.exists():
        with history_path.open('w') as f:
            f.write('{}')
    with history_path.open('r') as f:
        history = json.loads(f.read())
    current_week = week_number(today)

    def is_date_this_week_before_today(d):
        return (current_week == week_number(d)
                and d.date() < today)

    current_week_history = {(k, v) for (k, v) in history.items() if is_date_this_week_before_today(parse_date(k))}
    return dict(current_week_history)

def ordered_cafes(history):
    sorted_dates = sorted(history)
    cafes = []
    for cafe_date in sorted_dates:
        cafes.append(history[cafe_date])
    return cafes

def store_history(history):
    history_path = Path('history.json')
    with history_path.open('w') as f:
        f.write(json.dumps(history, sort_keys=True))

def update_history(history, today, todays_cafe):
    history[today.strftime('%d.%m.%Y')] = todays_cafe
    store_history(history)

today = date.today()
print('Today %s\n' % today.strftime('%d.%m.%Y'))

sodexo_terra_menu = get_sodexo_terra_menu(today)
print('\nSodexo Terra:\n\n%s' % make_readable(sodexo_terra_menu, collapse_whitespace=True))
daybreak_menu = get_daybreak_menu(today)
print('\nDayBreak:\n\n%s' % make_readable(daybreak_menu, collapse_whitespace=True))

weather = get_todays_weather()
print('\nWeather:\n\n temperature %s C\n chance of precipitation %s percent\n precipitation amount %s mm\n wind %s m/s' % (weather[TEMPERATURE], weather[PRECIPITATION_CHANCE], weather[PRECIPITATION_AMOUNT], weather[WIND]))

lunch_history = get_current_week_history(today)
current_week_cafes = ordered_cafes(lunch_history)
print('\nLunch history for current week:\n\n %s' % ', '.join(current_week_cafes))

cafes = deepcopy(CAFES)
cafes[SODEXO_TERRA]['menu'] = sodexo_terra_menu
cafes[DAYBREAK]['menu'] = daybreak_menu

food_taste = FoodTaste().preferences(FOOD_PREFERENCES)
weather_opinion = WeatherOpinion().weather(weather)
clo = ChiefLunchOfficer(food_taste=food_taste, weather_opinion=weather_opinion)
clo.lunched(current_week_cafes).weather(weather).cafes(cafes).weekday(today.weekday())
todays_cafes = clo.decide()
todays_cafe = todays_cafes[0]
todays_cafe_address = CAFES[todays_cafe]['address']
update_history(lunch_history, today, todays_cafe)
print('\nRecommendation:\n\n %s, %s' % (todays_cafe, todays_cafe_address))
formatted_cafes = ', '.join(todays_cafes[0:5]) + '\n' + ', '.join(todays_cafes[5:-1])
print('\nAll lunch in preferred order:\n\n %s' % (formatted_cafes))
