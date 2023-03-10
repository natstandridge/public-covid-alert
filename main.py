from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from twilio.rest import Client
import csv
import os
import configparser
from decimal import *

import time

class Subscriber:
    def __init__(self, name, phone_number, state, county, community_level, last_rate, current_rate, total_county_cases, total_state_cases, is_increasing):
        self.name = name
        self.phone_number = phone_number
        self.state = state
        self.county = county
        self.community_level = community_level ## Low, Medium or High
        self.last_rate = last_rate ## case rate per 100,000 for the previous week
        self.current_rate = current_rate ## case rate per 100,000 for the latest week (last_rate becomes current_rate when current_rate is updated)
        self.total_county_cases = total_county_cases
        self.total_state_cases = total_state_cases
        self.is_increasing = is_increasing

        self.real_path = os.path.dirname(os.path.realpath(__file__)) ## allows program to get path based on file location
        
    def create(self):
        ''' Adds initialized subscriber to CSV'''

        with open(os.path.abspath(os.path.join(os.getcwd(), 'subscribers.csv')), 'a') as outf:
            csv_writer = csv.writer(outf)
            print(f"Writing row {self.row}")
            csv_writer.writerow(self.row)
        outf.close()

    def update(self, row):
        ''' Takes subscriber data and updates their row in the CSV '''

        with open(os.path.join(self.real_path, 'subscribers.csv')) as inf, open(os.path.join(self.real_path, 'temp_subscribers.csv'), 'w') as outf:
            reader = csv.reader(inf)
            writer = csv.writer(outf)
            for line in reader:
                if len(line) == 0:
                    continue
                if line[0] == self.name:
                    print(f"Updating the following row in subscribers.csv: {row}")
                    writer.writerow(row)
                else:
                    writer.writerow(line)
                
            writer.writerows(reader)

        inf.close()
        outf.close()
        os.remove(os.path.join(self.real_path, 'subscribers.csv'))
        os.rename(os.path.join(self.real_path, 'temp_subscribers.csv'), os.path.join(self.real_path, 'subscribers.csv'))

    def scrape(self):
        ''' Scrapes covid.cdc.gov to update community_level and current_rate (with last_rate becoming the old current_rate)
            Data is released every Thursday
        '''
        
        def dwait(element):
            return(WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.XPATH, element))))

        def scrollto(element):
            driver.execute_script("return arguments[0].scrollIntoView(true);", element)

        ## chrome options and web driver
        chrome_options = Options()
        chrome_options.add_argument('--incognito')
        chrome_options.add_argument('--disable-extension')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument("--window-size=1920,1080") ## MUST set window size for headless to work
        chrome_options.add_argument('-–disable-gpu')
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

        ## begin covid.cdc.gov scrape
        driver.get('https://covid.cdc.gov/covid-data-tracker/#datatracker-home') ## data gets updated Mon-Fri by 8pm ET
        driver.maximize_window()
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})") ## removing bot fingerprint

        location_search_box = dwait("/html/body/div[7]/div[2]/main/div[3]/div/div/div[1]/div/div[2]/div[2]/div/div[1]/input")
        scrollto(location_search_box)
        location_search_box.send_keys(f"{self.county}, {self.state}")
        time.sleep(1) ## there has to be some small wait here
        search_btn = dwait("/html/body/div[7]/div[2]/main/div[3]/div/div/div[1]/div/div[2]/div[2]/div/div[1]/i")
        search_btn.click()

        time.sleep(5) ## have to make sure enough of a buffer exists for page to load (webdriverwait alone does not work)

        ## now on page for the county, begin collecting updated data and adding to instance
        self.community_level = dwait("/html/body/div[7]/div[2]/main/div[2]/div[3]/div/div[1]/div/table/tbody/tr[1]/td/div/div[1]/div[2]").text
        self.last_rate = self.current_rate
        self.current_rate = dwait("/html/body/div[7]/div[2]/main/div[2]/div[3]/div/div[1]/div/table/tbody/tr[2]/td[2]/span").text
        self.total_county_cases = dwait("/html/body/div[7]/div[2]/main/div[2]/div[6]/div[7]/div[2]/div/div[1]/div/div[1]/div[1]/div[2]/span").text

        driver.close()
        driver.quit() ## close and quit to open new page for state data

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

        ## go to state page for statewide total
        driver.get(f"https://covid.cdc.gov/covid-data-tracker/#county-view?list_select_state={self.state}&data-type=CommunityLevels")
        driver.maximize_window()
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})") ## removing bot fingerprint

        self.total_state_cases = dwait("/html/body/div[7]/div[2]/main/div[2]/div[6]/div[7]/div[2]/div/div[1]/div/div[1]/div[1]/div[2]/span").text

        driver.quit()

        if self.last_rate == 0 or float(self.last_rate) == 0.0:
            self.is_increasing = 'First Record'
        elif float(self.current_rate) > float(self.last_rate):
            self.is_increasing = True
        elif float(self.current_rate) == float(self.last_rate):
            self.is_increasing = 'Same'
        else:
            self.is_increasing = False

        self.row = [self.name, self.phone_number, self.state, self.county, self.community_level, self.last_rate, self.current_rate, self.total_county_cases, self.total_state_cases, self.is_increasing]

        return(self.row)

    def alert(self):
        ''' Texts the subscriber with their community COVID information. '''
        config = configparser.ConfigParser()
        config.read_file(open(os.path.join(self.real_path, 'config.txt')))
        account_sid = str(config.get('Twilio Credentials','account_sid')).replace("'",'')
        auth_token = str(config.get('Twilio Credentials','auth_token')).replace("'",'')
        messaging_service_sid = str(config.get('Twilio Credentials','messaging_service_sid')).replace("'",'')
        
        client = Client(account_sid, auth_token)

        ## conditionals for message creation
        if self.is_increasing == 'First Record': ## no previous rate recorded so directionality cannot be determined
            try:
                message = client.messages.create(  ## new user message
                    messaging_service_sid=messaging_service_sid,
                    body=f'DO NOT REPLY TO THIS NUMBER\nYou are now signed up for COVID Alert. Please contact Nat if you would like to be removed from the contact list. Your first report will not include directionality, but every subsequent report will - Example: The COVID rate in your community is UP.',
                    to=f'+{self.phone_number}' 
                    )
            except:
                print(f"Could not send new user message for {self.name}.")
            message_body = f'COVID rate per 100k people: {self.current_rate}\nTotal cases in your county: {self.total_county_cases}\nTotal cases in your state: {self.total_state_cases}\nGeneral county COVID level: {self.community_level}'
        elif self.is_increasing == True:
            message_body = f'The COVID rate in your community is UP {str(((Decimal(self.current_rate)/Decimal(self.last_rate)) - 1) * 100)[:4]}%.\n\nCOVID rate per 100k people: {self.current_rate}\nTotal cases in your county: {self.total_county_cases}\nTotal cases in your state: {self.total_state_cases}\nGeneral county COVID level: {self.community_level}'
        elif self.is_increasing == 'Same':
            message_body = f'The COVID rate in your community has not changed.\n\nCOVID rate per 100k people: {self.current_rate}\nTotal cases in your county: {self.total_county_cases}\nTotal cases in your state: {self.total_state_cases}\nGeneral county COVID level: {self.community_level}'
        else:
            message_body = f'The COVID rate in your community is DOWN {str(((Decimal(self.last_rate)/Decimal(self.current_rate)) - 1) * 100)[:4]}%.\n\nCOVID rate per 100k people: {self.current_rate}\nTotal cases in your county: {self.total_county_cases}\nTotal cases in your state: {self.total_state_cases}\nGeneral county COVID level: {self.community_level}'

        try:
            message = client.messages.create(  
                messaging_service_sid=messaging_service_sid,
                body=f'\n{self.name}, here is your COVID Risk Report:\n\n{message_body}',      
                to=f'+{self.phone_number}' 
            )
            print(f"{self.name} has been texted their alert.")
        except:
            print(f"Could not send COVID Alert text for {self.name}")

def main():
    subscriber_list = []
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'subscribers.csv'), 'r') as f:
        csv_reader = csv.reader(f)
        for row in csv_reader: ## loads all subscriber data into subscriber_list for updating
            if len(row) == 0: ## skip empty rows
                continue
            if row[0] == 'Name': ## skip column names
                continue
            subscriber_list.append(row)
    f.close()

    for subscriber_data in subscriber_list:
        new_sub_data = []
        subscriber = Subscriber(subscriber_data[0],subscriber_data[1],subscriber_data[2],subscriber_data[3],subscriber_data[4],subscriber_data[5],subscriber_data[6],subscriber_data[7],subscriber_data[8],subscriber_data[9])
        new_sub_data = subscriber.scrape() ## returns the latest data in a list
        subscriber.update(new_sub_data) ## updates row in the CSV
        subscriber.alert() ## sends the text

if __name__ == '__main__':
    main()