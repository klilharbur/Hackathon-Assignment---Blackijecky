import struct

# ============================================================================
#                                  קבועים (Constants)
# ============================================================================

# הגדרות הרשת הבסיסיות לפי הוראות התרגיל
SERVER_PORT_UDP = 13122  # הפורט שבו כולם מאזינים להצעות (Offers)
MAGIC_COOKIE = 0xabcddcba  # "סיסמת הכניסה" שמופיעה בתחילת כל הודעה
MSG_TYPE_OFFER = 0x2  # סוג הודעה: הצעת משחק (שרת -> לקוח)
MSG_TYPE_REQUEST = 0x3  # סוג הודעה: בקשת משחק (לקוח -> שרת)
MSG_TYPE_PAYLOAD = 0x4  # סוג הודעה: מהלך משחק (קלף או החלטה)


# ============================================================================
#                          פונקציות עזר (Helper Functions)
# ============================================================================

def pack_string(string_val, length):
    """
    פונקציית עזר שהופכת מחרוזת טקסט רגילה לרצף בייטים באורך קבוע.
    אם המחרוזת קצרה מדי - מוסיפה אפסים בסוף.
    אם המחרוזת ארוכה מדי - חותכת אותה.
    """
    # המרה מטקסט (str) לבייטים (bytes)
    encoded = string_val.encode('utf-8')
    # מילוי באפסים (padding) עד לאורך הרצוי וחיתוך במקרה הצורך
    return encoded.ljust(length, b'\x00')[:length]


def unpack_string(byte_val):
    """
    פונקציית עזר שהופכת רצף בייטים חזרה לטקסט נקי, ללא האפסים המיותרים.
    """
    # הסרת אפסים מיותרים מסוף המחרוזת והמרה חזרה לטקסט
    return byte_val.rstrip(b'\x00').decode('utf-8')


# ============================================================================
#                       1. הודעת הצעה (Offer Message)
#                       כיוון: מהשרת ללקוח (UDP Broadcast)
# ============================================================================

def pack_offer(server_port, server_name):
    """
    אריזת הודעת Offer.
    המבנה: [Cookie (4)] [Type (1)] [Port (2)] [Name (32)]
    """
    # הכנת השם באורך בדיוק 32 בייטים
    name_bytes = pack_string(server_name, 32)

    # האריזה עצמה בעזרת struct
    # ! = Network Endian (סדר בייטים אוניברסלי לרשת)
    # I = Unsigned Int (4 bytes) - בשביל ה-Cookie
    # B = Unsigned Char (1 byte) - בשביל ה-Type
    # H = Unsigned Short (2 bytes) - בשביל ה-Port
    # 32s = String (32 bytes) - בשביל השם
    return struct.pack('!IBH32s', MAGIC_COOKIE, MSG_TYPE_OFFER, server_port, name_bytes)


def unpack_offer(data):
    """
    פריקת הודעת Offer. משמש את הלקוח.
    מחזיר: (is_valid, server_port, server_name)
    """
    # בדיקת אורך: 4+1+2+32 = 39 בייטים
    if len(data) != 39:
        return False, None, None

    try:
        # פריקת הנתונים לפי אותו פורמט בדיוק
        cookie, msg_type, server_port, name_bytes = struct.unpack('!IBH32s', data)

        # בדיקה שההודעה תקינה (Cookie נכון ו-Type נכון)
        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_OFFER:
            return False, None, None

        server_name = unpack_string(name_bytes)
        return True, server_port, server_name

    except Exception:
        return False, None, None


# ============================================================================
#                       2. הודעת בקשה (Request Message)
#                       כיוון: מהלקוח לשרת (TCP)
# ============================================================================

def pack_request(num_rounds, team_name):
    """
    אריזת הודעת Request.
    המבנה: [Cookie (4)] [Type (1)] [Rounds (1)] [Name (32)]
    """
    name_bytes = pack_string(team_name, 32)
    # הפורמט: I (קוקי), B (סוג), B (מספר סיבובים - בייט אחד), 32s (שם)
    return struct.pack('!IBB32s', MAGIC_COOKIE, MSG_TYPE_REQUEST, num_rounds, name_bytes)


def unpack_request(data):
    """
    פריקת הודעת Request. משמש את השרת.
    מחזיר: (is_valid, num_rounds, team_name)
    """
    # בדיקת אורך: 4+1+1+32 = 38 בייטים
    if len(data) != 38:
        return False, None, None

    try:
        cookie, msg_type, rounds, name_bytes = struct.unpack('!IBB32s', data)

        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_REQUEST:
            return False, None, None

        team_name = unpack_string(name_bytes)
        return True, rounds, team_name

    except Exception:
        return False, None, None


# ============================================================================
#                       3. הודעות משחק (Payload Messages)
#                       יש שני סוגים שונים לאותו סוג הודעה (Type 4)
# ============================================================================

# --- א. הלקוח שולח החלטה (Hit/Stand) ---

def pack_payload_client(decision):
    """
    הלקוח שולח: "Hittt" או "Stand".
    המבנה: [Cookie (4)] [Type (1)] [Decision (5)]
    """
    # מוודאים שזה בדיוק 5 תווים (Hittt עם 3 t או Stand)
    decision_bytes = pack_string(decision, 5)
    return struct.pack('!IB5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision_bytes)


def unpack_payload_client(data):
    """
    השרת קורא את ההחלטה של הלקוח.
    """
    if len(data) != 10:  # 4 + 1 + 5 = 10
        return False, None
    try:
        cookie, msg_type, decision_bytes = struct.unpack('!IB5s', data)
        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
            return False, None
        return True, unpack_string(decision_bytes)
    except:
        return False, None


# --- ב. השרת שולח תוצאה וקלף ---

def pack_payload_server(result_code, card_rank, card_suit):
    """
    השרת שולח עדכון.
    המבנה: [Cookie (4)] [Type (1)] [Result (1)] [Rank (2)] [Suit (1)]
    Result: 0=ממשיכים, 1=תיקו, 2=הפסד, 3=ניצחון
    Rank: מספר הקלף (2-10 או ערכי תמונה)
    Suit: צורת הקלף (0-3)
    """
    # הפורמט: I (קוקי), B (סוג), B (תוצאה), H (דרגה - 2 בייטים), B (צורה)
    return struct.pack('!IBBHB', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, result_code, card_rank, card_suit)


def unpack_payload_server(data):
    """
    הלקוח מקבל עדכון מהשרת.
    """
    if len(data) != 9:  # 4 + 1 + 1 + 2 + 1 = 9
        return False, None, None, None
    try:
        cookie, msg_type, result, rank, suit = struct.unpack('!IBBHB', data)
        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
            return False, None, None, None
        return True, result, rank, suit
    except:
        return False, None, None, None