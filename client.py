import socket
import protocol
import sys

# ============================================================================
#                               הגדרות
# ============================================================================
BUFFER_SIZE = 1024

def read_exact(sock, n):
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data

def listen_for_offers():
    """
    שלב 1: האזנה לשידורי UDP כדי למצוא שרת.
    """
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # טריק כדי שיוכלו לרוץ כמה לקוחות על אותו מחשב
    try:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        # Windows fallback
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    udp_sock.bind(('', protocol.SERVER_PORT_UDP))

    print("Client started, listening for offer requests...")

    while True:
        # מחכים להודעה...
        data, addr = udp_sock.recvfrom(BUFFER_SIZE)

        # מנסים לפרוק את ההודעה
        is_valid, server_port, server_name = protocol.unpack_offer(data)

        if is_valid:
            server_ip = addr[0]
            print(f"Received offer from server '{server_name}' at address {server_ip}, attempting to connect...")
            udp_sock.close()
            return server_ip, server_port


def play_game(server_ip, server_port):
    """
    שלב 2+3: חיבור TCP וניהול המשחק
    """
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.settimeout(5)

    try:
        # 1. התחברות לשרת
        tcp_sock.connect((server_ip, server_port))
        print(f"Connected to {server_ip}:{server_port}")

        # 2. קבלת פרטים מהמשתמש
        # (אפשר לשנות את זה לקבוע אם רוצים אוטומציה)
        team_name = "Team Joker"
        try:
            num_rounds = int(input("How many rounds do you want to play? "))
        except:
            num_rounds = 3  # ברירת מחדל אם המשתמש הקיש שטויות

        # 3. שליחת הודעת Request (אני רוצה לשחק!)
        req_packet = protocol.pack_request(num_rounds, team_name)
        tcp_sock.sendall(req_packet)

        print("Request sent. Waiting for game to start...")

        # 4. לולאת המשחק (Game Loop)
        # אנחנו נשארים בלולאה הזו כל עוד השרת שולח לנו נתונים
        while True:
            # מחכים להודעה מהשרת (קלף או תוצאה)
            # אנחנו קוראים 9 בייטים כי זה הגודל של הודעת Payload מהשרת
            # (לפי החישוב ב-protocol.py: 4+1+1+2+1 = 9)
            data = read_exact(tcp_sock, 9)
            if data is None:
                print("Server disconnected.")
                break

    
            # פריקת ההודעה
            valid, result, rank, suit = protocol.unpack_payload_server(data)

            if not valid:
                print("Error: Received invalid packet from server.")
                continue

            # --- פענוח הקלפים לתצוגה יפה ---
            # המרת המספרים (1-13) לשמות (Ace, King...)
            ranks_map = {1: 'Ace', 11: 'Jack', 12: 'Queen', 13: 'King'}
            rank_str = ranks_map.get(rank, str(rank))  # אם לא בתמונה, תחזיר את המספר

            # המרת הצורות (0-3) לשמות
            suits_map = {0: 'Hearts', 1: 'Diamonds', 2: 'Clubs', 3: 'Spades'}
            suit_str = suits_map.get(suit, '?')

            # --- לוגיקת המשחק ---

            if result == 0:  # 0 = המשחק עדיין רץ, קיבלנו קלף
                print(f"Server sent card: {rank_str} of {suit_str}")

                # עכשיו תורנו להחליט!
                # נשאל את המשתמש מה לעשות
                action = input("Your move: [h]it or [s]tand? ").lower()

                if action == 'h':
                    decision = "Hittt"  # חייב להיות 5 תווים לפי הפרוטוקול
                else:
                    decision = "Stand"

                # שליחת התשובה לשרת
                msg = protocol.pack_payload_client(decision)
                tcp_sock.sendall(msg)

            elif result == 1:  # תיקו
                print(f"Round Over: It's a TIE! (Last card: {rank_str} of {suit_str})")

            elif result == 2:  # הפסד
                print(f"Round Over: You LOST! (Last card: {rank_str} of {suit_str})")

            elif result == 3:  # ניצחון
                print(f"Round Over: You WON! (Last card: {rank_str} of {suit_str})")

            # הערה: אם התוצאה היא 1,2,3 - אנחנו לא שולחים כלום חזרה,
            # אלא פשוט מחכים לסיבוב הבא (הלולאה תרוץ שוב).

    except Exception as e:
        print(f"Game error: {e}")
    finally:
        tcp_sock.close()
        print("Disconnected.")


def main():
    while True:
        # 1. חיפוש שרת
        ip, port = listen_for_offers()

        # 2. משחק
        play_game(ip, port)

        # 3. מנוחה קצרה לפני חיפוש חדש
        print("Looking for a new server in 3 seconds...")
        import time
        time.sleep(3)


if __name__ == "__main__":

    main()


