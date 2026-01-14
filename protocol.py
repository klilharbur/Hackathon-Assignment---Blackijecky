import struct


SERVER_PORT_UDP = 13122  # הפורט הקבוע שבו השרת משדר ב-UDP (כמו תחנת רדיו קבועה)
MAGIC_COOKIE = 0xabcddcba  # סיסמה לוודא שההודעה שייכת למשחק שלנו ולא סתם זבל ברשת
MSG_TYPE_OFFER = 0x2  # קוד סוג הודעה: הצעה (Offer) מהשרת (בייט אחד)
MSG_TYPE_REQUEST = 0x3  # קוד סוג הודעה: בקשת הצטרפות (Request) מהלקוח
MSG_TYPE_PAYLOAD = 0x4  # קוד סוג הודעה: מהלך במשחק (קלף שנשלח או החלטת שחקן)


def read_exact(sock, n):
    """
    מטרה: לקרוא מהרשת *בדיוק* n בייטים.
    למה צריך את זה? ב-TCP הודעות יכולות להגיע בחלקים. פונקציית recv רגילה עלולה להחזיר רק חלק מההודעה.
    הפונקציה הזו מבטיחה שלא נמשיך עד שאין לנו את כל החבילה ביד.
    """
    data = b''  # משתנה ריק (מסוג bytes) שיאגור את המידע שמגיע
    while len(data) < n:  # לולאה: כל עוד כמות הבייטים שאספנו קטנה מ-n (מה שביקשנו)
        try:
            # מנסים לקרוא מהסוקט. מבקשים רק את הכמות שחסרה לנו (n פחות מה שכבר יש)
            chunk = sock.recv(n - len(data))

            if not chunk:  # אם recv החזיר כלום (ריק), זה אומר שהצד השני ניתק את השיחה
                return None

            data += chunk  # מדביקים את החתיכה החדשה שהגיעה לערימה שלנו
        except:
            # אם הייתה שגיאת תקשורת כלשהי, מחזירים None כדי לסמן כישלון
            return None

    return data  # מחזירים את החבילה השלמה והמוכנה


# --- פונקציות לטיפול במחרוזות (Strings) ---

def pack_string(string_val, length):
    """
    מטרה: להפוך טקסט (כמו שם קבוצה) לרצף בייטים באורך קבוע.
    אם השם קצר מדי - מוסיפים אפסים בסוף.
    אם השם ארוך מדי - חותכים אותו.
    """
    encoded = string_val.encode('utf-8')  # המרה מטקסט רגיל לבינארי (בייטים)
    # ljust: מוסיף תווים ריקים (\x00) מצד ימין עד שמגיעים לאורך length
    # [:length]: מבטיח שאם המחרוזת הייתה ארוכה מדי, נחתוך אותה בדיוק לאורך המותר
    return encoded.ljust(length, b'\x00')[:length]


def unpack_string(byte_val):
    """
    מטרה: להפוך רצף בייטים חזרה לטקסט קריא ולנקות את ה"ריפוד" (האפסים).
    """
    # rstrip: מסיר את תווי ה-Null (\x00) מסוף המחרוזת (הריפוד שהוספנו קודם)
    # decode: הופך את הבייטים חזרה לטקסט (String)
    return byte_val.rstrip(b'\x00').decode('utf-8')


# ============================================================================
#                            פונקציות אריזה ופריקה (Packing/Unpacking)
# ============================================================================

# --- Offer (הודעת ההצעה ב-UDP) ---
def pack_offer(server_port, server_name):
    # קודם כל מכינים את השם שיהיה בדיוק 32 בייטים (עם ריפוד אפסים אם צריך)
    name_bytes = pack_string(server_name, 32)

    # הפקודה struct.pack הופכת משתנים לרצף בייטים אחד ארוך.
    # הפורמט '!IBH32s' אומר:
    # ! = Network Order (Big Endian) - חובה בתקשורת כדי שכל המחשבים יבינו את המספרים אותו דבר
    # I = Unsigned Int (4 בייטים) - עבור ה-Cookie
    # B = Unsigned Char (1 בייט) - עבור ה-Message Type
    # H = Unsigned Short (2 בייטים) - עבור הפורט (מספר עד 65,535 נכנס ב-2 בייטים)
    # 32s = מחרוזת של 32 בייטים - עבור שם השרת
    # סה"כ גודל: 4 + 1 + 2 + 32 = 39 בייטים
    return struct.pack('!IBH32s', MAGIC_COOKIE, MSG_TYPE_OFFER, server_port, name_bytes)


def unpack_offer(data):
    # בדיקת גודל: האם קיבלנו בדיוק 39 בייטים? אם לא, זו לא הודעת Offer תקינה
    if len(data) != 39:
        return False, None, None
    try:
        # הפקודה struct.unpack עושה את ההפך: לוקחת בייטים ומפרקת למשתנים
        cookie, msg_type, server_port, name_bytes = struct.unpack('!IBH32s', data)

        # בדיקות אבטחה: האם הסיסמה (Cookie) נכונה? האם סוג ההודעה הוא 0x2?
        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_OFFER:
            return False, None, None

        # המרה של בייטים השם חזרה לטקסט נקי
        server_name = unpack_string(name_bytes)

        # החזרת הנתונים המעובדים בהצלחה
        return True, server_port, server_name
    except:
        return False, None, None


# --- Request (הודעת הבקשה ב-TCP) ---
def pack_request(num_rounds, team_name):
    name_bytes = pack_string(team_name, 32)  # הכנת השם (32 בייטים)

    # הפורמט '!IBB32s':
    # I (4) - Cookie
    # B (1) - Type
    # B (1) - מספר הסיבובים (מספיק בייט אחד למספר קטן)
    # 32s - שם הקבוצה
    # סה"כ גודל: 4 + 1 + 1 + 32 = 38 בייטים
    return struct.pack('!IBB32s', MAGIC_COOKIE, MSG_TYPE_REQUEST, num_rounds, name_bytes)


def unpack_request(data):
    # אנחנו מצפים בדיוק ל-38 בייטים
    if len(data) != 38:
        return False, None, None
    try:
        cookie, msg_type, rounds, name_bytes = struct.unpack('!IBB32s', data)

        # וידוא שזו הודעת Request (סוג 0x3) והקוקי נכון
        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_REQUEST:
            return False, None, None

        team_name = unpack_string(name_bytes)
        return True, rounds, team_name
    except:
        return False, None, None


# --- Payload Client (החלטה: Hittt או Stand) ---
def pack_payload_client(decision):
    # כאן השדה הוא באורך 5 בייטים. המילה "Hittt" או "Stand" נכנסת בדיוק.
    decision_bytes = pack_string(decision, 5)

    # פורמט '!IB5s':
    # I (4) - Cookie
    # B (1) - Type
    # 5s (5) - המחרוזת של ההחלטה
    # סה"כ: 4 + 1 + 5 = 10 בייטים
    return struct.pack('!IB5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision_bytes)


def unpack_payload_client(data):
    # מצפים ל-10 בייטים
    if len(data) != 10:
        return False, None
    try:
        cookie, msg_type, decision_bytes = struct.unpack('!IB5s', data)
        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
            return False, None
        return True, unpack_string(decision_bytes)
    except:
        return False, None


# --- Payload Server (קלף או תוצאה) ---
def pack_payload_server(result_code, card_rank, card_suit):
    # פורמט '!IBBHB':
    # I (4) - Cookie
    # B (1) - Type (0x4)
    # B (1) - Result Code (0=Active, 1=Tie, 2=Loss, 3=Win)
    # H (2) - Card Rank (מספר הקלף, 1-13)
    # B (1) - Card Suit (צורה, 0-3)
    # סה"כ: 4 + 1 + 1 + 2 + 1 = 9 בייטים
    return struct.pack('!IBBHB', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, result_code, card_rank, card_suit)


def unpack_payload_server(data):
    # מצפים ל-9 בייטים
    if len(data) != 9:
        return False, None, None, None
    try:
        cookie, msg_type, result, rank, suit = struct.unpack('!IBBHB', data)
        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
            return False, None, None, None
        return True, result, rank, suit
    except:
        return False, None, None, None
