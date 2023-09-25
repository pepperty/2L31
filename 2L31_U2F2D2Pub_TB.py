'''
/*
 * Copyright 2010-2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * A copy of the License is located at
 *
 *  http://aws.amazon.com/apache2.0
 *
 * or in the "license" file accompanying this file. This file is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing
 * permissions and limitations under the License.
 */
 '''
 # PJ:XT PYT_BPU_Tank

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

import logging
import time
import json

# Sub process
import subprocess
import urllib.request

# log
import csv
import datetime

import RPi.GPIO as GPIO
import os
import time
import statistics

Alast = 0
Blast = 0
dist_A = 0
dist_B = 0
Max_Tank = 200
trMill = int(time.time())
tlMill = int(time.time())

# Define GPIO to use on Pi
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

IO_DET01 = 18
IO_DET02 = 23
IO_EXC01 = 24
IO_EXC02 = 25
IO_TRIG01 = 8
IO_TRIG02 = 7
IO_REL01 = 12
IO_REL02 = 16

# ULtrasonic trigger time
TRIGGER_TIME = 0.00001
MAX_TIME = 0.05  # max time waiting for response in case something is missed

GPIO.setup(IO_DET01, GPIO.IN)
GPIO.setup(IO_DET02, GPIO.IN)
GPIO.setup(IO_EXC01, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(IO_EXC02, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(IO_TRIG01, GPIO.OUT)
GPIO.setup(IO_TRIG02, GPIO.OUT)
GPIO.setup(IO_REL01, GPIO.OUT)
GPIO.setup(IO_REL02, GPIO.OUT)

# This function measures a distance
def measure(IO_TRIG,IO_EXC):
    # Pulse the trigger/echo line to initiate a measurement
    GPIO.output(IO_TRIG, True)
    time.sleep(TRIGGER_TIME)
    GPIO.output(IO_TRIG, False)

    # ensure start time is set in case of very quick return
    start = time.time()
    timeout = start + MAX_TIME

    # set line to input to check for start of echo response
    while GPIO.input(IO_EXC) == 0 and start <= timeout:
        start = time.time()

    if(start > timeout):
        return -1

    stop = time.time()
    timeout = stop + MAX_TIME
    # Wait for end of echo response
    while GPIO.input(IO_EXC) == 1 and stop <= timeout:
        stop = time.time()

    if(stop <= timeout):
        elapsed = stop-start
        distance = float(elapsed * 34300)/2.0
    else:
        return -1
    return distance
# Stop Node-RED
# if platform.system() == "Windows":
#     node_red_path = r'C:\Users\peppe\AppData\Roaming\npm\node-red.cmd'
#     subprocess.call(['taskkill', '/F', '/IM', 'node-red'])
#     subprocess.Popen([node_red_path])
# if platform.system() == "Linux":
#     subprocess.call(['killall', 'node-red'])
#     subprocess.Popen(['node-red'])

AllowedActions = ['both', 'publish', 'subscribe']

# Custom MQTT message callback
def customCallback(client, userdata, message):
    print("Received a new message: ")
    print(message.payload)
    print("from topic: ")
    print(message.topic)
    print("--------------\n\n")

# host = "aquiml1rupuga-ats.iot.ap-southeast-1.amazonaws.com"
# rootCAPath = "certs/AmazonRootCA1.pem"
# certificatePath = "certs/device.pem.crt"
# privateKeyPath = "certs/private.pem.key"

host = "a1x0dm3q26289z-ats.iot.ap-southeast-1.amazonaws.com"
rootCAPath = "/home/DEV01/2L31/certsP/AmazonRootCA1.pem"
certificatePath = "/home/DEV01/2L31/certsP/device.pem.crt"
privateKeyPath = "/home/DEV01/2L31/certsP/private.pem.key"

port = 8883
useWebsocket = False
clientId = "LIV24"
topic = "iot/boosterpump"

if not useWebsocket and (not certificatePath or not privateKeyPath):
    print("Missing credentials for authentication.")
    exit(2)

# Port defaults
if useWebsocket and not port:  # When no port override for WebSocket, default to 443
    port = 443
if not useWebsocket and not port:  # When no port override for non-WebSocket, default to 8883
    port = 8883

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

# Init AWSIoTMQTTClient
myAWSIoTMQTTClient = None
if useWebsocket:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId, useWebsocket=True)
    myAWSIoTMQTTClient.configureEndpoint(host, port)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath)
else:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
    myAWSIoTMQTTClient.configureEndpoint(host, port)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# AWSIoTMQTTClient connection configuration
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec

# Connect and subscribe to AWS IoT
mode = 'publish'
myAWSIoTMQTTClient.connect()
if mode == 'both' or mode == 'subscribe':
    myAWSIoTMQTTClient.subscribe(topic, 1, customCallback)
time.sleep(2)

def get_cpu_temperature():
    try:
        result = subprocess.check_output(["vcgencmd", "measure_temp"])
        temperature_str = result.decode("utf-8")
        temperature = float(temperature_str.split("=")[1].split("'")[0])
        return temperature
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

# Publish to the same topic in a loop forever
# Read data from JSON file
with open('/home/DEV01/2L31/2L31_BPU_TB.json', 'r') as file:
    json_data1 = json.load(file)
# print(json_data)
if __name__ == '__main__':
    while True:
        try:
            def connect(host='http://google.com'):
                try:
                    urllib.request.urlopen(host) #Python 3.x
                    return True
                except:
                    return False
            # Function to log the current timestamp
            def log_timestamp():
                current_time = datetime.datetime.now()
                return current_time.strftime("%Y-%m-%d %H:%M:%S")
            # Create a list to store log data
            log_data = []

            # Generate log data (you can do this whenever you want to log data)
            log_data.append(log_timestamp())

            # CSV filename
            csv_filename = "timestamps.csv"

            # Check if the file already exists
            file_exists = True
            try:
                with open(csv_filename, "r") as file:
                    reader = csv.reader(file)
                    if not list(reader):
                        file_exists = False
            except FileNotFoundError:
                file_exists = False

            # If the file doesn't exist, create it with a header row
            if not file_exists:
                with open(csv_filename, mode="w", newline="") as file:
                    writer = csv.writer(file)
                    ft_raw = ["Timestamp","ping","alarm","trouble"]
                    writer.writerow(ft_raw)  # Header row

            while connect():
                time.sleep(1)
                dist_A_list = []
                dist_B_list = []
                for i in range(10):
                    time.sleep(0.5)
                    Anow = measure(IO_TRIG01,IO_EXC01)
                    if(Anow > -1):
                        #if (Anow - Alast <50 and Anow - Alast > -50) or Alast == 0:
                        dist_A_list.append(Anow)
                        Alast = Anow
                    else:
                        dist_A_list.append(0)
                        print("#UA")
                        
                    time.sleep(0.5)
                    Bnow = measure(IO_TRIG02,IO_EXC02)
                    if(Bnow > -1):
                        #if (Bnow - Blast <50 and Bnow - Blast > -50) or Blast == 0:
                        dist_B_list.append(Bnow)
                        Blast = Bnow
                    else:
                        dist_B_list.append(0)
                        print("#UB")
                if len(dist_A_list)>0:
                    dist_A = Anow-round(min(dist_A_list),3)
                if len(dist_B_list)>0:
                    dist_B = round(min(dist_B_list),3)

                # Read the state of the GPIO pin
                DET01_state = GPIO.input(IO_DET01)
                DET02_state = GPIO.input(IO_DET02)
                print("################")
                print(Anow)
                print(Bnow)
                print(dist_A)
                print(dist_B)
                print(DET01_state)
                print(DET02_state)
                print("################")

                if mode == 'both' or mode == 'publish':
                    # print("################")
                    # print(json_data1['devices'][0]['tags'][2])
                    # print("################")
                    trMill = int(time.time())
                    if (trMill-tlMill)>30:
                        # Print the state (it should read LOW when the button is not pressed)
                        if DET01_state == GPIO.LOW:
                            json_data1['devices'][0]['tags'][0]['value'] = "Leak"
                        elif DET01_state == GPIO.HIGH:
                            json_data1['devices'][0]['tags'][0]['value'] = "Nomal"
                        if DET02_state == GPIO.LOW:
                            json_data1['devices'][1]['tags'][0]['value'] = "Leak"
                        elif DET02_state == GPIO.HIGH:
                            json_data1['devices'][1]['tags'][0]['value'] = "Nomal"

                        json_data1['devices'][0]['tags'][1]['value'] = dist_A
                        json_data1['devices'][1]['tags'][1]['value'] = dist_B

                        messageJson1 = json.dumps(json_data1)
                        myAWSIoTMQTTClient.publish(topic, messageJson1, 0)
                        tlMill = int(time.time())

                        # if mode == 'publish':
                        #     print('Published topic %s: %s\n' % (topic, messageJson1))
            # Reset by pressing CTRL + C
            time.sleep(30)
            # Append log data to the CSV file
            log_data.append(connect())
            log_data.append(json_data1['devices'][0]['tags'][0]['value'])
            log_data.append(json_data1['devices'][1]['tags'][0]['value'])
            with open(csv_filename, mode="a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(log_data)
        except KeyboardInterrupt:
            print("Measurement stopped by User")
            GPIO.cleanup()
        except Exception as e:
            print(f"An exception occurred: {str(e)}")
            pass
