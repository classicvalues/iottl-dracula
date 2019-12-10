#!/usr/bin/env python

import bson, json, time, uuid, re
import datetime
import paho.mqtt
import paho.mqtt.subscribe as subscribe
import paho.mqtt.client as mqtt
import base64
import logging
import traceback
from struct import *
from enum import Enum
from urllib.request import urlopen
logger = logging.getLogger('iottl.hermes')
from json import load
import socket, binascii, sys, os

class IPTools:
    
    # gets external IP, using four different methods in case of unavailability 
    @staticmethod
    def get_external_ip_address():

        try:
            my_ip = str(urlopen('http://ip.42.pl/raw').read(),'utf-8')
            return my_ip
        except:
            pass

        try:
            my_ip = str(load(urlopen('http://jsonip.com'))['ip'], 'utf-8')
            return my_ip
        except:
            pass


        try:
            my_ip = str(load(urlopen('http://httpbin.org/ip'))['origin'], 'utf-8')
            return my_ip
        except:
            pass


        try:
            my_ip = str(load(urlopen('https://api.ipify.org/?format=json'))['ip'], 'utf-8')
            return my_ip
        except:
            pass

        return None


    # gets internal address used to get to internet
    @staticmethod
    def get_my_ip_address():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            address = str(s.getsockname()[0])
            s.close()
            return address

class Hermes:

    FLAG_PERSISTS = 0x01        
    FLAG_PROXY    = 0x02    # used when sending BSON payload, in that case no default metadata will be added


    CLIENTS_STATUS_PREFIX = "dracula/clients"

    class Events(Enum):
        connected = 1
        disconnected = 2
    def __getclientid__(self):
        id = os.path.splitext(sys.argv[0])[0] + '@' +IPTools.get_external_ip_address()
        return id
    
   
    def __init__(self, server, port=1883, username=None, 
                password=None, cacert=None, clientid=None, 
                callback=None, statuscallback = None):

        # normally we want to be our messages / subscriptions
        # peristent however if there is no client_id specified 
        # we turn this feature off as it creates clutter on broker
        clean_session = False

        self.server = server
        self.port = port
        self.pubid = 0

        # if not uid specified generate one
        if not clientid:            
            clientid = self.__getclientid__()
            #str(base64.b32encode(uuid.uuid4().bytes)[:26], 'utf-8')
            clean_session = True
            
        self.clientid = clientid
        # in case of reconnect clean_session false means that subscriptions are restoreds
        self.mqttc = mqtt.Client(client_id = clientid, clean_session=clean_session)
        # generic subscription callback
        self.mqttc.subcallback = callback
        # specific callbacks
        self.mqttc.subcallbacks ={}
        
        self.statuscallback = statuscallback
        
        self.mqttc.owner = self
        
        # hardcoded login
        # TODO: proper authentication 

        if not username:
            raise ValueError('You need to provide username/password!')
        else:
            self.mqttc.username_pw_set(username, password)
        
        # Assign event callbacks
        self.mqttc.on_message = Hermes.__on_message
        self.mqttc.on_connect = Hermes.__on_connect
        self.mqttc.on_publish = Hermes.__on_publish
        self.mqttc.on_subscribe = Hermes.__on_subscribe
        self.mqttc.on_disconnect = Hermes.__on_disconnect
        self.mqttc.on_log = Hermes.__on_log

        if cacert:            
            self.mqttc.tls_set(cacert)
            # TODO: get rid of this once the DNS server name settles
            self.mqttc.tls_insecure_set(True) 

    def is_connected(self):
        return None


    def __construct_will_payload(self, online, legit):
        payload = {
            'clientid': self.clientid,
            'internalip': IPTools.get_my_ip_address(),
            'externalip': IPTools.get_external_ip_address(),            
            'timestamp': int(time.time()),
            'status': online,
            'clean': legit
        }
        return payload

    def connect(self):
        self.cleanconnect = True
        # Set will in case we loose connection
        self.mqttc.will_set(
            Hermes.CLIENTS_STATUS_PREFIX + '/%s' % (self.clientid), 
            json.dumps(self.__construct_will_payload(False, False)),
            2,
            True 
            )
        rc = self.mqttc.connect(self.server, self.port, 5)
        
        # Start subscribe, with QoS level 0
        if rc == 0:
            self.mqttc.loop_start()            
            return True
        else:
            return False


    def send(self, topic, dict, flags=0, qos = 0):

        if (flags & Hermes.FLAG_PROXY):                        
            dict['_sys_proxy_timestamp'] = int(time.time())
            dict['_sys_proxy_clientid'] = str(self.clientid)
            dict['_sys_proxy_pubid'] = self.pubid
        else:
            dict['_sys_timestamp'] = int(time.time())
            dict['_sys_clientid'] = self.clientid
            dict['_sys_pubid'] = self.pubid

        self.pubid+=1
        data = bson.dumps(dict)
        self.send_raw(topic, data, flags, qos)


    def send_raw(self, topic, payload=None, flags=0, qos = 0):
        if (flags & Hermes.FLAG_PERSISTS):
            ret = True
        else:
            ret = False

        self.mqttc.publish(topic, payload, qos, retain=ret)


    def __handle_status_callback( self, callbacktype, **kwargs):
        if self.statuscallback:
            self.statuscallback( self, callbacktype, **kwargs)



    def subscribe(self, topic, callback = None, qos=1):
        if callback:
            # check if there is any wildchar
            if topic.find('*')!=-1 or topic.find('#')!=-1:
                raise Exception("can't set specific handler for {0} as it contains wildcards and is thus ambigious".format(topic))
            if topic not in self.mqttc.subcallbacks:
                self.mqttc.subcallbacks[topic] = ( callback, qos )
            else:
                raise Exception("topic {0} is already registered.".format(topic))
        else:
            self.mqttc.subcallbacks[topic] = ( None, qos )


        self.mqttc.subscribe(topic, qos)

    def unsubscribe(self, topic):
        if topic in self.mqttc.subcallbacks:
            del self.mqttc.subcallbacks[topic]            
            self.mqttc.unsubscribe(topic)
        else:
            raise Exception("Not a such topic registered {0}".format(topic))


    def disconnect(self):
        self.mqttc.publish(
            Hermes.CLIENTS_STATUS_PREFIX + '/%s' % (self.clientid), 
            json.dumps(self.__construct_will_payload(False, True)),
            2,
            True 
            )    
        self.mqttc.disconnect()    


    # mqtt callbacks
    @staticmethod
    def __on_connect(mosq, obj, flags, rc):
        logger.info("connect %d" % (rc))
        if rc == 5:
            mosq.disconnect()
        elif rc==0:
            # if it is a reconnect            
            if not mosq.owner.cleanconnect:            
                logger.warning("re-registering callbacks")
                # try to register what we have
                for i in mosq.subcallbacks.items():
                    logger.warning(i[0])
                    mosq.subscribe( i[0],  i[1][1] )

            mosq.owner.cleanconnect = False     
            print ("connect....")       
            mosq.publish(
                Hermes.CLIENTS_STATUS_PREFIX +'/%s' % (mosq.owner.clientid), 
                json.dumps(mosq.owner.__construct_will_payload(True, True)),
                2,
                True 
            )                


    @staticmethod
    def __on_message(mosq, obj, msg):
        
        payload = None
        # try to detect BSON
        if len(msg.payload)>4:            
            if unpack('I', bytes(msg.payload[:4]))[0] == len(msg.payload):
                try:
                    payload =  bson.loads(msg.payload)
                except:
                    pass

        if not payload:
            payload = msg.payload

        try:

            if msg.topic in mosq.subcallbacks and mosq.subcallbacks[msg.topic][0]:
                mosq.subcallbacks[msg.topic][0](mosq.owner, msg.topic, payload)	
            
            elif mosq.subcallback:
                mosq.subcallback(mosq.owner, msg.topic, payload)	

        except Exception as exp:
            traceback.print_exc()

    @staticmethod
    def __on_publish(mosq, obj, mid):
        pass

    @staticmethod
    def __on_subscribe(mosq, obj, mid, granted_qos):
        pass

    @staticmethod
    def __on_disconnect(mosq, obj, rc):
        logger.info("disconnect with code [%d]" % (rc) )
        
       
        pass

    @staticmethod
    def __on_log(mosq, obj, level, string):
        logger.info(string)
        pass
        
if __name__ == "__main__":
    pass
