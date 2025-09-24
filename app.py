import socket
import threading
import datetime
import select
import time
import os

class ChatServer:
    def __init__(self, host="0.0.0.0", port=None):
        # Use Render's PORT environment variable or default to 5000
        self.host = host
        self.port = port or int(os.getenv('PORT', 5000))
        self.clients = {}  # {username: (ip, conn)}
        self.chat_history = []
        self.running = False
        self.server_socket = None
        
    def store_message(self, sender, message):
        """Store message with timestamp"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {sender}: {message}"
        self.chat_history.append(entry)
        return entry
        
    def get_help(self):
        return (
            "\nAvailable commands:\n"
            "  list                       → list all connected users\n"
            "  broadcast <msg>            → send message to everyone\n"
            "  send <username> <msg>      → private message to user\n"
            "  exit                       → disconnect\n"
        )
        
    def broadcast_message(self, message, exclude_username=None):
        """Send a message to all connected clients except the excluded one."""
        disconnected_users = []
        for username, (_, conn) in self.clients.items():
            if username == exclude_username:
                continue
            try:
                conn.sendall(message.encode('utf-8'))
            except (ConnectionResetError, BrokenPipeError):
                disconnected_users.append(username)
                
        # Remove disconnected users
        for username in disconnected_users:
            if username in self.clients:
                print(f"Removing disconnected user: {username}")
                self.clients[username][1].close()
                del self.clients[username]
                
    def handle_client(self, conn, addr):
        ip = addr[0]
        username = None
        try:
            # Get username with timeout
            conn.settimeout(5.0)
            username = conn.recv(1024).decode('utf-8').strip()
            conn.settimeout(None)
            
            if not username:
                conn.close()
                return
                
            # Check if username already exists
            if username in self.clients:
                conn.sendall("Username already taken. Disconnecting.".encode('utf-8'))
                conn.close()
                return
                
            self.clients[username] = (ip, conn)
            join_msg = f"{username}@{ip} joined the chat"
            print(f"[+] {join_msg}")
            self.store_message("Server", join_msg)
            self.broadcast_message(f"[Server] {username} joined the chat", exclude_username=username)
            
            # Send welcome message
            welcome_msg = f"Welcome to the chat, {username}! Type 'help' for commands."
            conn.sendall(welcome_msg.encode('utf-8'))
            
            while self.running:
                try:
                    # Use select to check for data with timeout
                    read_sockets, _, _ = select.select([conn], [], [], 1.0)
                    if conn in read_sockets:
                        data = conn.recv(4096).decode('utf-8').strip()
                        if not data:
                            break
                            
                        entry = self.store_message(f"{username}@{ip}", data)
                        print(f"{entry}")
                        
                        # Handle commands
                        if data == "list":
                            response = "Connected clients:\n" + "\n".join(
                                [f"  {u}@{i}" for u, (i, _) in self.clients.items()]
                            )
                            conn.sendall(response.encode('utf-8'))
                            
                        elif data.startswith("broadcast "):
                            msg = data.replace("broadcast ", "", 1)
                            broadcast_msg = f"[BROADCAST from {username}] {msg}"
                            self.broadcast_message(broadcast_msg, exclude_username=username)
                            
                        elif data.startswith("send "):
                            parts = data.split(" ", 2)
                            if len(parts) == 3:
                                target_user, msg = parts[1], parts[2]
                                if target_user in self.clients:
                                    _, t_conn = self.clients[target_user]
                                    try:
                                        t_conn.sendall(
                                            f"[Private from {username}] {msg}".encode('utf-8')
                                        )
                                    except (ConnectionResetError, BrokenPipeError):
                                        conn.sendall(f"User {target_user} is not connected.".encode('utf-8'))
                                else:
                                    conn.sendall(f"User {target_user} not found.".encode('utf-8'))
                            else:
                                conn.sendall("Usage: send <username> <message>".encode('utf-8'))
                                
                        elif data == "exit":
                            break
                            
                        else:
                            conn.sendall(self.get_help().encode('utf-8'))
                            
                except socket.timeout:
                    continue
                except (ConnectionResetError, BrokenPipeError):
                    break
                    
        except Exception as e:
            print(f"[!] Error with {ip}: {e}")
        finally:
            if username and username in self.clients:
                leave_msg = f"{username}@{ip} left the chat"
                print(f"[-] {leave_msg}")
                self.store_message("Server", leave_msg)
                self.broadcast_message(f"[Server] {username} left the chat", exclude_username=username)
                del self.clients[username]
            conn.close()
            
    def start(self):
        """Start the chat server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"[*] Chat Server started on {self.host}:{self.port}")
        print(f"[*] Server URL: https://your-app-name.onrender.com")
        print("[*] Press Ctrl+C to stop the server")
        
        try:
            while self.running:
                # Use select to check for new connections with timeout
                read_sockets, _, _ = select.select([self.server_socket], [], [], 1.0)
                if self.server_socket in read_sockets:
                    conn, addr = self.server_socket.accept()
                    client_thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                    client_thread.daemon = True
                    client_thread.start()
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            self.running = False
            # Close all client connections
            for username, (_, conn) in self.clients.items():
                try:
                    conn.sendall("Server is shutting down. Goodbye!".encode('utf-8'))
                    conn.close()
                except:
                    pass
            self.server_socket.close()
            print("Server stopped.")

if __name__ == "__main__":
    import sys
    
    # Get port from environment variable (Render provides this)
    port = int(os.getenv('PORT', 5000))
    
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port number. Using default port 5000.")
            
    server = ChatServer(port=port)
    server.start()