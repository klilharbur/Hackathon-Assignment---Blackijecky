import socket
import threading
import time
import random
import protocol # ייבוא הקובץ המשותף שמגדיר איך אורזים ופורקים הודעות

# הגדרות כלליות לשרת
SERVER_NAME = "OneByteWinners"
BROADCAST_IP = '255.255.255.255'  # כתובת מיוחדת ששולחת לכל מי שנמצא ברשת המקומית (UDP)

# קבועים עבור תוצאת הסיבוב (לפי הפרוטוקול שהגדרתם)
RESULT_GAME_ACTIVE = 0 # המשחק עדיין רץ, שולחים קלף
RESULT_TIE = 1         # תיקו
RESULT_LOSS = 2        # הפסד של השחקן (הדילר ניצח)
RESULT_WIN = 3         # ניצחון של השחקן

# פונקציה שהופכת נתוני קלף (מספר וצורה) לטקסט קריא למשתמש
def get_card_name(rank, suit):
    ranks = {1: 'Ace', 11: 'Jack', 12: 'Queen', 13: 'King'} # שמות מיוחדים למספרים
    suits = {0: 'Hearts', 1: 'Diamonds', 2: 'Clubs', 3: 'Spades'} # שמות הצורות
    r_str = ranks.get(rank, str(rank)) # אם זה לא 1, 11, 12, 13 - פשוט קח את המספר כטקסט
    s_str = suits.get(suit, '?') # אם הצורה לא מוכרת, שים סימן שאלה
    return f"[{r_str}-{s_str}]" # מחזיר פורמט כמו [Ace-Spades]

# פונקציה ליצירת חפיסת קלפים חדשה
def create_deck():
    deck = []
    for suit in range(4): # 4 צורות
        for rank in range(1, 14): # 13 קלפים בכל צורה
            deck.append((rank, suit)) # הוספת הקלף כצמד (Tuple) לחפיסה
    random.shuffle(deck) # ערבוב החפיסה בצורה אקראית
    return deck

def calculate_hand_value(hand):
    total = 0
    aces = 0
    for rank, suit in hand:
        if rank == 1: # אם זה אס
            aces += 1
            total += 11 # בהתחלה נחשיב אותו כ-11
        elif rank >= 10: # נסיך, מלכה, מלך שווים 10
            total += 10
        else: # שאר הקלפים שווים את ערכם המספרי
            total += rank

    # לוגיקת האס: אם עברנו את 21, נהפוך אסים מ-11 ל-1 כדי לא להישרף
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

# משיכת קלף מהחפיסה
def draw_card(deck):
    if not deck: return (0, 0) # אם נגמרו הקלפים (לא אמור לקרות)
    return deck.pop() # מוציא ומחזיר את הקלף האחרון בחפיסה

# טריק למציאת ה-IP הפנימי של המחשב שלי ברשת
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # אנחנו לא באמת מתחברים, רק בודקים דרך איזה כרטיס רשת המחשב היה יוצא לאינטרנט
        s.connect(("8.8.8.8", 80))
        my_ip = s.getsockname()[0] # קבלת הכתובת של כרטיס הרשת הפעיל
        s.close()
        return my_ip
    except:
        return "127.0.0.1" # אם אין אינטרנט, חזור לכתובת המקומית

# --- תהליך השידור ב-UDP ---
# פונקציה שרצה בנפרד ו"צועקת" לכולם שהשרת קיים
def broadcast_offers(tcp_port):
    my_ip = get_local_ip()
    print(f"Server started, listening on IP address {my_ip}")

    # יצירת סוקט UDP (DGRAM)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # הגדרה שמאפשרת לסוקט הזה לשלוח הודעות Broadcast לכולם
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        # הצמדת הסוקט ל-IP שלי (חשוב כדי לוודא שאנחנו ברשת הנכונה)
        udp_sock.bind((my_ip, 0))
        print(f"UDP socket bound successfully to {my_ip}")
    except Exception as e:
        print(f"Notice: Could not bind UDP to {my_ip}. Error: {e}")

    # אריזת הודעת ההצעה לפי הפרוטוקול (כולל פורט ה-TCP שבו השרת מחכה)
    packet = protocol.pack_offer(tcp_port, SERVER_NAME)

    while True: # לולאה אינסופית
        try:
            # שליחת החבילה לכל המחשבים ברשת בפורט 13122
            udp_sock.sendto(packet, (BROADCAST_IP, protocol.SERVER_PORT_UDP))
            time.sleep(1) # המתנה של שנייה בין שידור לשידור
        except Exception as e:
            print(f"Broadcast error: {e}")
            time.sleep(1)

# --- ניהול הלקוח ב-TCP ---
# פונקציה שמתעוררת עבור כל לקוח שמתחבר
def handle_client(client_socket, addr):
    print(f"New connection from {addr}")
    # אם הלקוח לא שולח כלום במשך 60 שניות, ננתק אותו (מניעת תקיעת משאבים)
    client_socket.settimeout(120.0)

    try:
        # שלב 1: קבלת הודעת Request (שם קבוצה וסיבובים) - גודל 38 בייטים
        data = protocol.read_exact(client_socket, 38)
        if not data: return # אם הלקוח התנתק מיד

        # פריקת הנתונים
        valid, num_rounds, team_name = protocol.unpack_request(data)
        if not valid:
            print(f"Invalid request from {addr}")
            return

        print(f"Game started with {team_name}. Rounds requested: {num_rounds}")

        # שלב 2: לולאת המשחק לפי מספר הסיבובים שהלקוח ביקש
        for round_num in range(1, num_rounds + 1):
            print(f"\n--- Round {round_num}/{num_rounds} vs {team_name} ---")

            deck = create_deck() # חפיסה חדשה לכל סיבוב
            player_hand = [] # יד השחקן

            # דילר לוקח 2 קלפים (אחד יהיה גלוי ואחד מוסתר)
            dealer_hand = [draw_card(deck), draw_card(deck)]
            # שחקן מקבל 2 קלפים
            card1 = draw_card(deck)
            card2 = draw_card(deck)
            player_hand.extend([card1, card2])

            # הדפסה ללוג השרת כדי שנדע מה קורה
            d_val = calculate_hand_value(dealer_hand)
            print(f"  Dealer Hand: {[get_card_name(r, s) for r, s in dealer_hand]} ({d_val})")

            # שליחת 2 הקלפים של השחקן ללקוח (הודעות Payload באורך 9 בייטים)
            try:
                client_socket.sendall(protocol.pack_payload_server(RESULT_GAME_ACTIVE, card1[0], card1[1]))
                client_socket.sendall(protocol.pack_payload_server(RESULT_GAME_ACTIVE, card2[0], card2[1]))
                # שליחת רק הקלף הראשון של הדילר (השני נשאר "סוד" בינתיים)
                first_dealer_card = dealer_hand[0]
                client_socket.sendall(
                    protocol.pack_payload_server(RESULT_GAME_ACTIVE, first_dealer_card[0], first_dealer_card[1]))
            except socket.error as e:
                print(f"Error sending cards: {e}")
                return

            player_bust = False # משתנה שבודק אם השחקן נשרף (עבר 21)

            # שלב 3: תור השחקן (Hit/Stand)
            while True:
                # בדיקה אם השחקן עבר את 21
                if calculate_hand_value(player_hand) > 21:
                    player_bust = True
                    break # השחקן נשרף, התור נגמר

                print("Waiting for player decision...")
                # קבלת החלטה מהלקוח (10 בייטים לפי הפרוטוקול)
                data = protocol.read_exact(client_socket, 10)
                if not data: return # הלקוח התנתק

                valid_dec, decision = protocol.unpack_payload_client(data)
                if not valid_dec: return

                print(f"Player sent: '{decision}'")

                if decision == "Stand":
                    break # השחקן סיים את תורו מרצונו
                elif decision == "Hittt":
                    # השחקן ביקש קלף נוסף
                    new_card = draw_card(deck)
                    player_hand.append(new_card)
                    print(f"Dealt card {get_card_name(new_card[0], new_card[1])} to player.")
                    # שליחת הקלף החדש ללקוח
                    client_socket.sendall(protocol.pack_payload_server(RESULT_GAME_ACTIVE, new_card[0], new_card[1]))

            # שלב 4: תור הדילר (רק אם השחקן לא נשרף קודם)
            round_result = 0
            if player_bust:
                round_result = RESULT_LOSS # השחקן נשרף -> הפסד מיידי
                print(f"Player busted! ({calculate_hand_value(player_hand)})")
            else:
                print("Dealer Logic:")
                dealer_val = calculate_hand_value(dealer_hand)
                # חוק הבלאק ג'ק: הדילר חייב למשוך קלפים עד שיגיע ל-17 לפחות
                while dealer_val < 17:
                    new_d_card = draw_card(deck)
                    dealer_hand.append(new_d_card)
                    dealer_val = calculate_hand_value(dealer_hand)
                    print(f"  Dealer hits: {get_card_name(new_d_card[0], new_d_card[1])}. Total: {dealer_val}")

                # שלב 5: קביעת המנצח
                player_val = calculate_hand_value(player_hand)
                if dealer_val > 21: # הדילר נשרף
                    round_result = RESULT_WIN
                elif dealer_val > player_val: # הדילר קרוב יותר ל-21
                    round_result = RESULT_LOSS
                elif player_val > dealer_val: # השחקן קרוב יותר ל-21
                    round_result = RESULT_WIN
                else: # תיקו
                    round_result = RESULT_TIE

            # שלב 6: שליחת הודעה סופית לסיבוב (כוללת את קוד התוצאה)
            last = player_hand[-1] # שולחים את הקלף האחרון כחלק מהמבנה
            client_socket.sendall(protocol.pack_payload_server(round_result, last[0], last[1]))
            print(f"Result sent: {round_result}")

    except Exception as e:
        print(f"Error with client {addr}: {e}")
    finally:
        # סגירת החיבור בסיום כל הסיבובים או בשגיאה
        client_socket.close()
        print(f"Closed connection {addr}")

# הפונקציה הראשית
def main():
    # יצירת סוקט TCP (STREAM)
    server_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # bind לפורט 0 גורם למערכת ההפעלה למצוא פורט פנוי באופן אוטומטי
    server_tcp.bind(('', 0))
    # התחלת האזנה לחיבורים נכנסים
    server_tcp.listen()
    # בירור הפורט שקיבלנו מהמערכת
    server_port = server_tcp.getsockname()[1]

    # הפעלת ה-Thread של ה-UDP.
    # daemon=True אומר שהתהליכון הזה ימות אוטומטית כשהתוכנית הראשית תיסגר
    t = threading.Thread(target=broadcast_offers, args=(server_port,), daemon=True)
    t.start()

    # לולאת השרת הראשית: מחכה ללקוחות חדשים לנצח
    while True:
        try:
            # עצירה והמתנה ללקוח חדש (Three-way handshake)
            client, addr = server_tcp.accept()
            # ברגע שמישהו התחבר, פתח לו תהליכון (Thread) נפרד ומיד תחזור לחכות ללקוח הבא
            threading.Thread(target=handle_client, args=(client, addr)).start()
        except Exception as e:
            print(f"Accept error: {e}")

# נקודת הכניסה לתוכנית
if __name__ == "__main__":
    main()
