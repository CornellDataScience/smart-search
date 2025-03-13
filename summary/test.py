import requests
import json
import time
from collections import deque

class WeatherDataProcessor:
    def __init__(self, api_key, cache_size=5):
 
        self.api_key = api_key
        self.cache = deque(maxlen=cache_size)

    def fetch_weather_data(self, city):

        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.api_key}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            self.cache.append((city, data, time.time()))
            return data
        else:
            raise ValueError(f"Failed to fetch weather data for {city}")

    def get_cached_weather(self, city):
 
        for cached_city, data, timestamp in self.cache:
            if cached_city == city and time.time() - timestamp < 600:  # 10-minute cache
                return data
        return None

    def analyze_weather(self, weather_data):

        temp = weather_data["main"]["temp"] - 273.15  # Convert Kelvin to Celsius
        conditions = weather_data["weather"][0]["description"]
        wind_speed = weather_data["wind"]["speed"]

        summary = f"Temperature: {temp:.2f}°C, Conditions: {conditions}, Wind Speed: {wind_speed} m/s."
        if temp > 30:
            summary += " It's quite hot today!"
        elif temp < 10:
            summary += " It's quite chilly!"
        return summary

    def get_weather_summary(self, city):
 
        cached_data = self.get_cached_weather(city)
        if cached_data:
            return "Cached Data: " + self.analyze_weather(cached_data)
        
        try:
            weather_data = self.fetch_weather_data(city)
            return self.analyze_weather(weather_data)
        except ValueError as e:
            return str(e)