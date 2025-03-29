"""
    Built from sample code for Multi-Threaded Server
    
    Author: Jordan Beard
    zID: z5473030
    
"""
import ast
import random
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
from Crypto.Random import get_random_bytes
from collections import defaultdict
from Crypto.Protocol.SecretSharing import Shamir
import hmac, hashlib

#global variables for sharing between threads
recvQ = queue.Queue()
TCP_recvQ = queue.Queue()
clientAlive = False
print_lock = threading.Lock()
recvQ_lock = threading.Lock()
TCP_recvQ_lock = threading.Lock()

# Server would be running on the same host as Client
if len(sys.argv) != 6:
    print("\n===== Error usage, python3 TCPClient3.py SERVER_IP SERVER_PORT CLIENT_UDP ======\n")
    sys.exit(0)
    
#checking conditions on t, n, and k are met
if not sys.argv[1].isdigit() or not int(sys.argv[1]) in [15,18,21,24,27,30] \
                or not sys.argv[2].isdigit() or int(sys.argv[2]) < 3\
                    or not sys.argv[3].isdigit() or int(sys.argv[3])<5\
                        or not int(sys.argv[2]) <  int(sys.argv[3]):
    print("Invalid input")
    print("\n === Error usage, need k >= 3, n >= 5, and k < n\n")
    sys.exit(0)


#initialising variables to determine protocols
t= int(sys.argv[1])
k= int(sys.argv[2])
n= int(sys.argv[3])
Dt = (t*6*6)/60         #period for DBF deletion, needs to be converted to mins
DBF_period = t*6        #DBF generation period, needs to be converted to seconds

#array for tracking udp
contacts = defaultdict(list)


#threading receiver flag 
receiver_off = threading.Event()
clientAlive = True

#Server host & port
serverHost = sys.argv[4]
serverPort = int(sys.argv[5])

#get ip address of the client
host_name = gethostname()
local_ip = gethostbyname(host_name)
broadcast_ip = '255.255.255.255'



#generate random 32 byte value foundation for EphID
#new for each client
long_secret = os.urandom(32)


#UDP receive method for handling incoming packets
def udp_receive():
    
    #ensure global variables are used
    global recvQ
    global recvQ_lock

    #Initialise a UDP socket '' listens to broadcast on port 5005
    udp_socket = socket(AF_INET, SOCK_DGRAM)
    udp_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    udp_socket.bind(('', 5005)) 
    
    #loop constantly to listen to packets
    while True:
        #listen to data constantly, currently just prints to terminal window
        data = udp_socket.recv(1024)
        
        #drop half the packets per spec
        num = random.randint(1, 10)
        
        #drop any packets if number in range 1 -> 5 inclusive
        if num < 6:
            
            #split seperate packets arriving in the bytestream.
            data = data.decode().split("\n\r")
            
            #print using print lock
            time.sleep(1)
            print_to_screen(f"[UDP recv] {data}")
    
            #put in receive Q using receive lock to manage later
            with recvQ_lock:
                for i in data:
                    if not i == "" and not i == " ":
                        recvQ.put(i)


#Generate an Emphemeral ID
def generate_EphID():
    
    #global variable, long term 32-Byte value
    global long_secret
    
    #Get current time
    current_time = int(time.time())

    #Use current time, given t, to generate unique current time identifier
    time_slot = (current_time//t).to_bytes(8, byteorder='big')

    #HMAC for final EphID
    ephid = hmac.new(long_secret, time_slot, hashlib.sha256).digest()
    
    print(f"Generated EphID: {ephid.hex()}")
    
    return ephid
    
#method for broadcasting data
def udp_send():

    #global variables
    global k, n
    
    
    while clientAlive:
        
        #EphID   
        secret_bytes = generate_EphID()
        
        #Split EphID to apply Shamir twice
        secret_bytes1 = secret_bytes[0:16]
        secret_bytes2 = secret_bytes[16:]
        
        #Apply shamir to both parts
        a_shares = Shamir.split(k, n, secret_bytes1)
        b_shares = Shamir.split(k, n, secret_bytes2)
        
        #Generate packets to transmit
        packets = []
        
        #Hash complete ID for final check
        hash_check = hashlib.sha256(secret_bytes).digest()
        
        # Encode the share bytes as hex so they can be safely stored as strings.
        for i in range(len(a_shares)):
            packets.append(f"{i+1}|{a_shares[i][1].hex()}|{b_shares[i][1].hex()}|{hash_check}\n\r")
        
        
        #broadcast address and port
        send_address = (broadcast_ip, 5005)
        
        #define udp socket
        udp_socket = socket(AF_INET, SOCK_DGRAM)  
        udp_socket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        
        #sequence for EPhID
        time_sub = 0
        
        
        #send details to listening port 
        for packet in packets:
            
            #broadcast every 3 seconds subtracting time it takes to complete send
            sleep_time = max(0, time_sub)
            time.sleep(3-time_sub)
            
            st = time.perf_counter()
            #broadcast on defined address
            udp_socket.sendto(f"{packet}".encode(), send_address)
            
            #print with lock to show we are receiving
            print_to_screen(f"[UDP send] {packet}")
            
            #time at end method to subtract
            end = time.perf_counter()
            time_sub = end-st
        
            

#ethod for vairous threads printing to screen
def print_to_screen(content):
    
    #print lock to make sure print to screen safe
    global print_lock
    
    with print_lock:
        print(content)


#method for receiver method to loop and add to the receiving Q
def receiver(clientSocket):
    
    #locks
    global TCP_recvQ
    global TCP_recvQ_lock
    
    while not receiver_off.is_set():
        
        #graceful handling of disconnection
        try:
            data = clientSocket.recv(1024)
                
            if not data:
                break
            
            #split seperate packets in bytestream so seperate packets
            #aren't combined
            data = data.decode().split("\n\r")
    
            with TCP_recvQ_lock:
                for i in data:
                    if not i == "" and not i == " ":
                        TCP_recvQ.put(i)
        except(ConnectionResetError, OSError):
            break
    

#Message to handle and signal received messages
#Specifically handling incoming UDP broadcasts
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
        
        #get message from recvQ
        with recvQ_lock:
            received_message = recvQ.get()
        
       
        #split on defined value
        packet = received_message.split("|")
        
        #add to defaultdictionary with key the hex literal of final hash
        #append to array the first three values in array
        contacts[ast.literal_eval(packet[3])].append(packet[:3])


        #arrays to combine different 
        a = []
        b = []
    
        #check the values in the dictionary to see if length up to k
        #shamir combine if any apply
        for key, value in contacts.copy().items():
            if len(value) >= k:
                for packet in value:
                    
                    #append values to respective arrays for combination
                    a.append((int(packet[0]), int(packet[1], 16)))
                    b.append((int(packet[0]), int(packet[2], 16)))

                #combine both arrays seperately
                key_a = Shamir.combine(a)
                key_b = Shamir.combine(b)
                
                #concatenate first half and second half of EPhID
                rebuilt_secret = key_a + key_b
                
                
                #
                if key == hashlib.sha256(rebuilt_secret).digest():
                    #DO METHOD FOR DEFFIE HELMEN HERE
                    print("++++ secret retrieved +++++")
                    
                    #remove from contacts so not repeating same methods
                    contacts.pop(key, None) 
                    
                else:
                    
                    #remove if hash not correct as unable 
                    #to determine which value corrupted
                    contacts.pop(key, None) 
                    

                
        
        
#These methods create TCP connection and handle incoming messages
#Still using a "receiver thread" which is probably unnecessary in this case
#but allows receipt on connection while other methods are running
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
    
    
    connected = True
   
    while connected:
           
        while(TCP_recvQ.empty()):
            continue
     
        with TCP_recvQ_lock:
            receivedMessage = TCP_recvQ.get()
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
   
           
    while(TCP_recvQ.empty()):
        continue
     
    with TCP_recvQ_lock:
        receivedMessage = TCP_recvQ.get()
        
    if receivedMessage == "QBF request":
            
            
            #FILL METHOD FOR SENDING QBF DATA
            
            #STOP GENERATING QBF
        with TCP_recvQ_lock:
            receivedMessage = TCP_recvQ.get()
            
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
                
        
#Start threads for UDP receipt
message_thread = threading.Thread(target=udp_receive, args = ())
message_thread.daemon = True
message_thread.start()

message_thread = threading.Thread(target=udp_send, args = ())
message_thread.daemon = True
message_thread.start()

message_thread = threading.Thread(target=message_handler, args = ())
message_thread.daemon = True
message_thread.start()



while True:
    time.sleep(2)
    #send_covid_infected()




