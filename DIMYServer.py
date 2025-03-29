"""
    Built from sample code for Multi-Threaded Server
    
    Author: Jordan Beard
    zID: z5473030
    
"""
from socket import *
from threading import Thread
import threading
import queue
import sys, select
from datetime import datetime, timedelta
import select
from pathlib import Path

# acquire server host and port from command line parameter
#set the serverhost to localhost and given port
serverHost = "127.0.0.1"
serverPort = int(sys.argv[1])
serverAddress = (serverHost, serverPort)

#define locks for multithreading
active_client_lock = threading.Lock()
log_lock = threading.Lock()
userlog_lock = threading.Lock()

#define global variables
date_formatting = "%d %a %Y %H:%M:%S"

#tracking the current users for quick access by the server
active_clients = []
aliases = []


#reset active userlog
with open("userlog.txt", "w") as file:
    file.write("");
     

#Multithreading client example used to implement multiple clients on one server
#https://www.youtube.com/watch?v=nmzzeAvQHp8
def add_client(alias, socket):
    
    #adding client for shared access of server threads
    try:
        with active_client_lock:
            
            #remove previous occurrences (crashed client)
            if alias in aliases:
                index = aliases.index(alias)
                aliases.remove(alias)
                active_clients.remove(active_clients[index])
               
            #append new values
            active_clients.append(socket)
            aliases.append(alias)
        
       
        print(f"[join] {alias} joined\n")
    except:
       
        print(f"[join fail] {alias} failed to join\n")
    

#remove client from 
def remove_client(alias):
    try:
        with active_client_lock:
            
            index = aliases.index(alias)
            
            #remove client from trackers
            aliases.remove(alias)
            client = active_clients[index]
            active_clients.remove(client)
            
            #gracefully close client
            client.close()

            print(f"[left] {alias} left\n")
    except:

        print(f"[failure] {alias} leave failed\n")
        
#method for thread to message its own client
def message_my_client(client, content):
    try:
        with active_client_lock:
            
            client.send((content+"\n\r").encode())
        
        return True 
    except:
        
        print(f"[send failure] {content} failed\n")



#method for extracting messages from bytestream
#add to q for processing
def message_receiver(client, q, recvQ_lock):
    
    #continue until app closes ("daemon thread")
    while True:
        try:
            data = client.recv(1024).decode()
            if not data:
                break
            
            data = data.split("\n\r")
        except (ConnectionResetError, OSError) as e:
            data = "error"
            data = data.split("\n\r")

        with recvQ_lock:
            for i in data:
                if not i == "":
                    q.put(i)
                           

# define socket for the server side and bind address
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(serverAddress)

#setting up the option to reuuse the port 
serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)   
 
#class for each clients thread management
class ClientThread(Thread):
    def __init__(self, clientAddress, clientSocket):
        
        Thread.__init__(self)
        
        #initialisingclient variables
        self.clientAddress = clientAddress
        self.clientSocket = clientSocket
        self.recvQ = queue.Queue()
        self.recvQ_lock = threading.Lock()
        
        print()
        print(f"===== New connection created for:  {clientAddress}\n")
        self.clientAlive = True
        
    def run(self):
        
            message = ''
        
        #try:

            #initialise threaed for managing clients received messages
            recv_thread = threading.Thread(target= message_receiver, args = (self.clientSocket, self.recvQ, self.recvQ_lock,))
            recv_thread.daemon = True
            recv_thread.start()      
            
            while self.clientAlive:
        
                #retrieved separated messages q
                while self.recvQ.empty():
                    continue 
                    
                    #get message from handler
                with self.recvQ_lock:
                    message = self.recvQ.get()
                    print(f"[server rcv] {message} \n")
        
                    
                if message == "infected":
                    message = "CBF request"
                    try:
                        message_my_client(self.clientSocket, message)
                        print("[server send] CBF request \n")
                    except (BrokenPipeError, ConnectionResetError, OSError) as e:
                        print(f"[Connection lost]: {clientAddress}")
                        break
                        
                        
                elif message == "infection query":
                    message = "QBF request"
                    try:
                        message_my_client(self.clientSocket, message)
                        print("[server send] QBF request \n")
                    except (BrokenPipeError, ConnectionResetError, OSError) as e:
                        print(f"[Connection lost]: {clientAddress}")
                        break
                        
                    while self.recvQ.empty():
                        continue
                       
                    #get message from handler
                    with self.recvQ_lock:
                        message = self.recvQ.get()
                    print(f"[server rcv] {message} \n")
                    
                    #Insert Method for handling query
                    result = None
                    
                    if result == False:
                        message = "no contact"
                        message_my_client(self.clientSocket, message)
                    elif result == True:
                        message = "contact"
                        message_my_client(self.clientSocket, message)
                    elif message == "error":
                        print(f"[Connection lost]: {clientAddress}")
                        break
                    
                elif message == "error":
                    print(f"[Connection lost]: {clientAddress}")
                    break
                    
            
            print()
            print(f"===== Disconnection for:  {clientAddress}\n")
                    

print("\n===== Server is running =====")
print("===== Waiting for connection request from clients...=====")

#start listening for clients
while True:
    serverSocket.listen()
    clientSockt, clientAddress = serverSocket.accept()
    clientThread = ClientThread(clientAddress, clientSockt)    
    clientThread.start()


if __name__ == '__main__':
    
    c = ClientThread('localhost', 1025)