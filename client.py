import socket
import protocol  # הקובץ המשותף שלנו שמכיל את חוקי האריזה/פריקה
import time

BUFFER_SIZE = 1024  # גודל הזיכרון שאנחנו מקצים לקליטת הודעה בודדת ב-UDP



def get_card_name(rank, suit):
    """ הופכת את המספרים של הקלף לשם קריא (למשל: Ace of Spades) """
    ranks = {1: 'Ace', 11: 'Jack', 12: 'Queen', 13: 'King'}
    suits = {0: 'Hearts', 1: 'Diamonds', 2: 'Clubs', 3: 'Spades'}
    r_str = ranks.get(rank, str(rank))
    s_str = suits.get(suit, '?')
    return f"{r_str} of {s_str}"


def calculate_client_hand(hand_list):
    """ מחשבת את סכום הקלפים ביד, כולל טיפול באס (1 או 11) """
    total = 0
    aces = 0
    for rank, suit in hand_list:
        if rank == 1:
            aces += 1
            total += 11
        elif rank >= 10:
            total += 10
        else:
            total += rank
    # אם עברנו את 21 ויש לנו אס, נהפוך אותו ל-1
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total



def listen_for_offers():
    """
    מטרה: למצוא שרת ברשת.
    הלקוח פותח "רדיו" ומאזין לתדר 13122 עד שהוא שומע שרת משדר.
    """

    # 1. יצירת סוקט UDP
    # AF_INET = שימוש בכתובות IPv4 (כמו 192.168.1.5)
    # SOCK_DGRAM = פרוטוקול UDP (שליחת הודעות ללא חיבור קבוע, כמו מכתבים או רדיו)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 2. הגדרות סוקט מיוחדות (Socket Options)
    try:
        # SO_REUSEPORT: פקודה שמאפשרת לכמה תוכנות במחשב להאזין לאותו פורט במקביל.
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        # ב-Windows הפקודה REUSEPORT לא קיימת, אז משתמשים ב-REUSEADDR שעושה עבודה דומה.
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # 3. Bind - "פתיחת האוזניים"
    # הפקודה הזו אומרת למערכת ההפעלה: "כל הודעה שמגיעה לפורט 13122, תעבירי אליי".
    # ה-'' (מחרוזת ריקה) אומר: "תקבל הודעות מכל כרטיסי הרשת שלי".
    udp_sock.bind(('', protocol.SERVER_PORT_UDP))
    print(f"Client started, listening for offer requests on port {protocol.SERVER_PORT_UDP}...")

    while True:
        try:
            # 4. recvfrom - ההמתנה
            # הפקודה הזו עוצרת את התוכנית (Block) עד שמגיעה הודעה.
            # data = הבייטים שהגיעו (ההודעה הבינארית).
            # addr = הכתובת של מי ששלח (ה-IP של השרת).
            data, addr = udp_sock.recvfrom(BUFFER_SIZE)

            # 5. בדיקת תקינות (Unpacking)
            # מנסים לפרק את ההודעה לפי הפרוטוקול שלנו (בודקים Magic Cookie וסוג הודעה).
            valid, port, name = protocol.unpack_offer(data)

            if valid:
                # מצאנו שרת חוקי!
                print(f"Received offer from server '{name}' at {addr[0]}, attempting to connect...")

                # סוגרים את ה-UDP כי סיימנו את שלב החיפוש.
                udp_sock.close()

                # מחזירים את ה-IP של השרת (addr[0]) ואת הפורט TCP שלו שקיבלנו בהודעה
                return addr[0], port

        except Exception as e:
            print(f"UDP Error: {e}")


# ============================================================================
#                        שלב ב: מהלך המשחק (TCP Game Loop)
# ============================================================================

def play_game(server_ip, server_port):
    """
    מטרה: לנהל את החיבור והמשחק מול השרת שנבחר.
    כאן עוברים לתקשורת TCP - שיחה רציפה ואמינה.
    """

    # 1. יצירת סוקט TCP
    # SOCK_STREAM = פרוטוקול TCP (חיבור קבוע, אמין, סדר מובטח).
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # הגנה: אם השרת נתקע ולא עונה דקה, הסוקט יזרוק שגיאה ונתנתק.
    tcp_sock.settimeout(120.0)

    stats = {'wins': 0, 'losses': 0, 'ties': 0}
    num_rounds = 0

    try:
        # 2. Connect - "התקשרות" (3-Way Handshake)
        # כאן הלקוח יוצר קשר פיזי עם השרת.
        tcp_sock.connect((server_ip, server_port))
        print(f"Connected to server!\n")

        team_name = "Team KlilIdan"

        # קבלת כמות הסיבובים מהמשתמש
        try:
            user_input = input("How many rounds to play? ")
            if user_input.strip() == "":
                num_rounds = 3
            else:
                num_rounds = int(user_input)
        except ValueError:
            print("Invalid input. Defaulting to 3 rounds.")
            num_rounds = 3

        # 3. שליחת בקשה (Sendall)
        # אורזים את השם ומספר הסיבובים לחבילה בינארית (38 בייטים) ושולחים לשרת.
        tcp_sock.sendall(protocol.pack_request(num_rounds, team_name))

        my_hand = []
        dealer_shown_card = None
        round_counter = 1

        print(f"=== Starting Game ({num_rounds} rounds) ===")

        # --- לולאת המשחק המרכזית ---
        while True:
            # 4. קריאת הודעה מהשרת
            # אנחנו משתמשים ב-read_exact (מהקובץ protocol) ולא ב-recv רגיל.
            # למה? כי ב-TCP מידע זורם כמו נהר. אנחנו רוצים לוודא שקיבלנו בדיוק 9 בייטים
            # של הודעת שרת, ולא חצי הודעה.
            data = protocol.read_exact(tcp_sock, 9)

            if not data:
                print("Server disconnected.")
                break  # אם השרת ניתק, יוצאים

            # 5. פריקת ההודעה (Unpack)
            # הופכים את ה-9 בייטים למספרים: תוצאה, מספר קלף, צורה.
            valid, result, rank, suit = protocol.unpack_payload_server(data)
            if not valid:
                print("Invalid packet received.")
                break

            card_tuple = (rank, suit)

            # --- בדיקת תוצאה (לוגיקה) ---

            # אם Result שונה מ-0, סימן שהשרת מודיע על סוף סיבוב
            if result != 0:
                print(f"\nRound Result: ", end="")
                if result == 1:
                    print("It's a TIE!")
                    stats['ties'] += 1
                elif result == 2:
                    print("You LOST! (Dealer won)")
                    stats['losses'] += 1
                elif result == 3:
                    print("You WON!")
                    stats['wins'] += 1

                print("----------------------------------")

                # מאפסים את היד לקראת הסיבוב הבא
                my_hand = []
                dealer_shown_card = None
                round_counter += 1

                # הפקודה continue מחזירה אותנו לתחילת ה-while לחכות להודעה הבאה
                continue

            # === אם הגענו לפה, Result הוא 0, כלומר המשחק פעיל וקיבלנו קלף ===

            # ניהול לוגיקה מקומית: מי קיבל את הקלף? אני או הדילר?
            # ההיגיון: 2 הקלפים הראשונים שמגיעים הם שלי. השלישי הוא של הדילר.
            if len(my_hand) < 2:
                my_hand.append(card_tuple)
            elif dealer_shown_card is None:
                dealer_shown_card = card_tuple

                # ברגע שיש לי 2 קלפים ולדילר 1 - תורי לשחק!
                print(f"\n=== Round {round_counter} of {num_rounds} ===")
                my_hand_str = [get_card_name(r, s) for r, s in my_hand]
                print(f"Your hand: {my_hand_str} (Total: {calculate_client_hand(my_hand)})")
                print(f"Dealer shows: [{get_card_name(dealer_shown_card[0], dealer_shown_card[1])}]")

                goto_decision(tcp_sock)  # קוראים לפונקציה שמבקשת קלט ושולחת לשרת
            else:
                # אם כבר יש לי יד והדילר חשוף, וקיבלתי עוד קלף - סימן שביקשתי Hit
                print(f"Server sent card: [{get_card_name(rank, suit)}]")
                my_hand.append(card_tuple)

                # מדפיסים מצב עדכני
                my_hand_str = [get_card_name(r, s) for r, s in my_hand]
                total = calculate_client_hand(my_hand)
                print(f"Your hand: {my_hand_str} (Total: {total})")

                # אם לא נשרפתי (מעל 21), השרת מחכה לעוד החלטה שלי
                if total <= 21:
                    goto_decision(tcp_sock)

    except Exception as e:
        print(f"Game error: {e}")
    finally:
        # בסוף תמיד סוגרים את הסוקט כדי לשחרר משאבים
        tcp_sock.close()

        # חישוב והדפסת אחוזי הצלחה
        wins = stats['wins']
        if num_rounds > 0:
            win_rate = (wins / num_rounds) * 100
        else:
            win_rate = 0.0
        print(f"Finished playing {num_rounds} rounds, win rate: {win_rate:.1f}%")


def goto_decision(sock):
    """
    פונקציית עזר: מטפלת בקלט מהמשתמש ושולחת אותו לשרת.
    """
    while True:
        action = input("\nYour move: [H]it or [S]tand? ").lower()
        if action in ['h', 's']:
            break

    # השרת מצפה למילה "Hittt" (עם 3 תווים t) כדי למלא בדיוק 5 בייטים.
    # הלקוח כותב רק 'h', והקוד כאן מתרגם את זה לפרוטוקול הנכון.
    decision = "Hittt" if action == 'h' else "Stand"

    if decision == "Stand":
        print("You chose to Stand. Waiting for dealer...")

    # שליחת ההחלטה (10 בייטים) לשרת
    sock.sendall(protocol.pack_payload_client(decision))


def main():
    # הלולאה הראשית של התוכנית
    while True:
        # שלב 1: מצא שרת
        ip, port = listen_for_offers()

        # שלב 2: שחק מולו
        play_game(ip, port)

        # שלב 3: חפש שוב
        print("Looking for a new server in 3 seconds...")
        time.sleep(3)


if __name__ == "__main__":
    main()
