from socket  import *
HOST = 'localhost'
PORT = 5000
s = socket(AF_INET, SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)
(conn, addr) = s.accept()  # returns new socket and addr. client 
print(addr, "connected")
while True:                # forever
  data = conn.recv(1024)   # receive data from client
  print("received: "+data.decode())
  if not data: break       # stop if client stopped
  conn.send((data.decode()+"*").encode()) # return sent data plus an "*"
conn.close()               # close the connection
