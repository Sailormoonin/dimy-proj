"""
    Built from sample code for Multi-Threaded Server
    
    Python 3
    
    Usage:  python3 TCPClient3.py SERVER_IP SERVER_PORT CLIENT_UDP
    
    coding: utf-8
    
    Base author: (Tutor for COMP3331/9331)
    
    Final author: Jordan Beard
    zID: z5473030
    
"""

from socket import *
import sys
from User import User
import select
import threading
import queue
import time
import os
from pathlib import Path
import sys
import binascii

#global variables for sharing between threads
recvQ = queue.Queue()
clientAlive = False
print_lock = threading.Lock()
recvQ_lock = threading.Lock()

# Server would be running on the same host as Client
if len(sys.argv) != 6:
    print("\n===== Error usage, python3 TCPClient3.py SERVER_IP SERVER_PORT CLIENT_UDP ======\n")
    sys.exit(0)
    
'''
if not sys.argv[1].isdigit() or not int(sys.argv[1]) in [15,18,21,24,27,30] \
                or not sys.argv[2].isdigit() or int(sys.argv[2]) < 3\
                    or not sys.argv[3].isdigit() or int(sys.argv[3])<5\
                        or not int(sys.argv[2]) <  int(sys.argv[3]):
    print("Invalid input")
    print("\n === Error usage, need k >= 3, n >= 5, and k < n\n")
    sys.exit(0)
'''

#initialising variables to determine protocols
t= int(sys.argv[1])
k= int(sys.argv[2])
n= int(sys.argv[3])
Dt = (t*6*6)/60         #period for DBF deletion, needs to be converted to mins
DBF_period = t*6        #DBF generation period, needs to be converted to seconds

#threading receiver flag 
receiver_off = threading.Event()


#Server host & port
serverHost = sys.argv[4]
serverPort = int(sys.argv[5])

#get ip address of the client
host_name = gethostname()
local_ip = gethostbyname(host_name)
broadcast_ip = '255.255.255.255'


def udp_receive():
    
    global recvQ
    global recvQ_lock

    #Initialise a UDP socket '' listens to broadcast on port 5005
    udp_socket = socket(AF_INET, SOCK_DGRAM)
    udp_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    udp_socket.bind(('', 5005)) 
    
    while True:
        #listen to data constantly, currently just prints to terminal window
        data = udp_socket.recv(1024)
        data = data.decode().split("\n\r")
        
        #print using print lock
        time.sleep(1)
        print_to_screen(f"[UDP recv] {data}")

        #put in receive Q using receive lock to manage later
        with recvQ_lock:
            for i in data:
                if not i == "" and not i == " ":
                    recvQ.put(i)
    
        
#method for broadcasting data
def udp_send():

    #broadcast address and port
    send_address = (broadcast_ip, 5005)
    
    #define udp socket
    udp_socket = socket(AF_INET, SOCK_DGRAM)  
    udp_socket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    
    #sequence for EPhID
    sequence = 0
    
    while True:
    #send details to listening port 
        time.sleep(3)
        
        #broadcast on defined address
        udp_socket.sendto(f"{sequence}|listening?".encode(), send_address)
        
        #print with lock to show we are receiving
        print_to_screen(f"[UDP send] {sequence}")
        
        #increment sequence
        sequence+=1
        


#ethod for vairous threads printing to screen
def print_to_screen(content):
    
    global print_lock
    
    with print_lock:
        print(content)


#method for receiver method to loop and add to the receiving Q
def receiver(clientSocket):
    
    #locks
    global recvQ
    global recvQ_lock
    
    while not receiver_off.is_set():
        try:
            data = clientSocket.recv(1024)
                
            if not data:
                break
            
        
            data = data.decode().split("\n\r")
    
            with recvQ_lock:
                for i in data:
                    if not i == "" and not i == " ":
                        recvQ.put(i)
        except(ConnectionResetError, OSError):
            break
    

#Message to handle and signal received messages

'''

THIS IS CURRENTLY UNUSED BUT USEFUL WHEN DEALING WITH 
LOTS OF RECEIVED UDP BROADCAST MESSAGES
HANDLE ONE AT A TIME

'''

def message_handler():
    
    #global variables for sharing among threads
    global recvQ
    global recvQ_lock
    global clientAlive
    
    while clientAlive:
        
        #get received messages
        #wait for message in Q
        while(recvQ.empty()):
            if not clientAlive:
                break
            continue
        
        if not clientAlive:
            break
        
        with recvQ_lock:
            received_message = recvQ.get()
        
        
        data_split = received_message.split("|")
        
        #EXAMPLES OF MANAGING RECEIVED MESSAGES
        if received_message == "logout-success":
            print()
            print("==  ** == Thanks for stopping by == ** == ")
            print()
            clientAlive = False
            break
        
        #Handle received messages example from previous assignment
        if received_message == "":
            print_to_screen("[recv] Message from server is empty!")
            
        elif received_message.split("|")[0] == "cannot-message-group":
            print_to_screen(f"Failed to message group {received_message.split('|')[1]}")
            continue
        
        

def send_covid_infected():
    
    global receiver_on
    
    # initialise server address
    serverAddress = (serverHost, serverPort)

    # define a socket for the client side, it would be used to communicate with the server
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    
    # build connection with the server and send message to it
    clientSocket.connect(serverAddress)
    
    #Start receiver thread 
    recv_thread = threading.Thread(target= receiver, args = (clientSocket,))
    recv_thread.daemon = True
    recv_thread.start()     
    
    #send some message indicating we are want to notify about infection
    clientSocket.send("infected".encode())
    print(f"[client send] infected notification")
    
    #u
    connected = True
   
    while connected:
           
        while(recvQ.empty()):
            continue
     
        with recvQ_lock:
            receivedMessage = recvQ.get()
            print_to_screen(f"[Client recv] {receivedMessage}")
            
        
        if receivedMessage == "CBF request":
            
            print_to_screen(f"Processing CBF request")
            #FILL METHOD FOR SENDING CBF DATA
            
            #STOP GENERATING QBF
            
            connected = False
            
    receiver_off.set()
    try:
        clientSocket.shutdown(SHUT_RDWR)
    except:
        pass
    clientSocket.close()
    recv_thread.join()
    receiver_off.clear()

def request_infected_contact():
    
    global receiver_on
    
    serverAddress = (serverHost, serverPort)


    # define a socket for the client side, it would be used to communicate with the server
    clientSocket = socket(AF_INET, SOCK_STREAM)

    # build connection with the server and send message to it
    clientSocket.connect(serverAddress)
    
    #Start receiver thread 
    receiver_on = True
    recv_thread = threading.Thread(target= receiver, args = (clientSocket,))
    recv_thread.daemon = True
    recv_thread.start()     
    
    #begin login process
    clientSocket.send("contact_request".encode())
    print(f"[client send] infected notification")
    
    logged_in = True
   
           
    while(recvQ.empty()):
        continue
     
    with recvQ_lock:
        receivedMessage = recvQ.get()
        
    if receivedMessage == "QBF request":
            
            
            #FILL METHOD FOR SENDING QBF DATA
            
            #STOP GENERATING QBF
        with recvQ_lock:
            receivedMessage = recvQ.get()
            
        if receivedMessage == "no contact":
            pass
        elif receivedMessage == "contact":
            pass
        
    receiver_off.set()
    try:
        clientSocket.shutdown(SHUT_RDWR)
    except:
        pass
    clientSocket.close()
    recv_thread.join()
    receiver_off.clear()
                
        
 
#start thread to handle received messages
#message_thread = threading.Thread(target=message_handler, args = ())
#message_thread.daemon = True
#message_thread.start()

message_thread = threading.Thread(target=udp_receive, args = ())
message_thread.daemon = True
message_thread.start()

message_thread = threading.Thread(target=udp_send, args = ())
message_thread.daemon = True
message_thread.start()



while True:
    time.sleep(2)
    send_covid_infected()




