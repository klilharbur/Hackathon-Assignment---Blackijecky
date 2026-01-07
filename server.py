import socket
import threading
import time
import protocol  # זה הקובץ שיצרנו קודם - המילון המשותף

# ============================================================================
#                               הגדרות
# ============================================================================
SERVER_NAME = "OneByteWinners"  # השם שיופיע אצל הלקוחות
# שיניתי לכתובת המפורשת כדי למנוע בעיות ב-Windows
BROADCAST_IP = '255.255.255.255'


# ============================================================================
#                            פונקציות עזר
# ============================================================================

def get_local_ip():
    """
    מטרה: לגלות מה ה-IP האמיתי שלי ברשת (למשל 192.168.1.15).
    למה זה מסובך? כי למחשב יש גם כתובת פנימית (127.0.0.1) שלא עוזרת לאחרים.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # אנחנו לא באמת שולחים מידע לגוגל, רק "מכוונים" לשם
        # כדי שהמערכת תגיד לנו דרך איזה כרטיס רשת היינו יוצאים החוצה
        s.connect(("8.8.8.8", 80))
        my_ip = s.getsockname()[0]
        s.close()
        return my_ip
    except Exception:
        return "127.0.0.1"  # ברירת מחדל אם אין אינטרנט


# ============================================================================
#                        טרד 1: הכרוז (UDP)
# ============================================================================

def broadcast_offers(tcp_port):
    """
    הפונקציה הזו רצה במקביל לתוכנית הראשית (בטרד נפרד).
    תפקיד: לצעוק כל שנייה "אני פה! בואו לשחק בפורט X".
    tcp_port: המספר של ה"חדר הפרטי" שבו השרת מחכה לחיבורים.
    """
    print(f"Server started, listening on IP address {get_local_ip()}")

    # 1. פתיחת "רדיו" לשידור (UDP)
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 2. אישור מיוחד לשדר לכולם (Broadcast)
    # בלי השורה הזו, מערכת ההפעלה תחסום אותנו משיקולי אבטחה
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # 3. אריזת ההודעה לפי הפרוטוקול
    # אנחנו הופכים את המספרים לבייטים כדי שכולם יבינו
    packet = protocol.pack_offer(tcp_port, SERVER_NAME)

    # 4. הלולאה האינסופית של הכרוז
    while True:
        try:
            # שליחה לכתובת 255.255.255.255 בפורט 13122
            udp_sock.sendto(packet, (BROADCAST_IP, protocol.SERVER_PORT_UDP))

            # לישון שנייה אחת. זה קריטי!
            # אם לא נישן, המחשב ישלח מיליון הודעות בשנייה והמעבד יתקע.
            time.sleep(1)

        except Exception as e:
            print(f"Broadcast error: {e}")


# ============================================================================
#                        טרד 2: הדילר (Client Handler)
# ============================================================================

def handle_client(client_socket, addr):
    """
    הפונקציה הזו נוצרת מחדש עבור כל שחקן שמתחבר.
    כאן יתנהל כל משחק הבלאק-ג'ק.
    """
    print(f"New connection from {addr}")

    # --- כאן תכתבי את לוגיקת המשחק בהמשך ---
    # כרגע זה רק מדפיס וסוגר

    client_socket.close()


# ============================================================================
#                        התוכנית הראשית (Main Thread)
# ============================================================================

def main():
    # 1. פתיחת הדלת הראשית (TCP Socket)
    # SOCK_STREAM = חיבור אמין ורציף (TCP)
    server_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 2. תביאי לי פורט פנוי
    # bind מקבלת (IP, Port). ה-IP ריק (הכל), והפורט הוא 0.
    # 0 זה קוד למערכת ההפעלה: "אין לי כוח לבחור, תני לי פורט פנוי אקראי".
    server_tcp.bind(('', 0))

    # 3. פתיחת החנות
    server_tcp.listen()

    # 4. בדיקה איזה פורט קיבלנו
    # בגלל שביקשנו 0, אנחנו חייבים לשאול את המערכת "מה נתת לי?"
    # כדי שנוכל לשלוח את המספר הזה בשידורי ה-UDP
    server_port = server_tcp.getsockname()[1]

    # 5. הפעלת הטרד של הכרוז (broadcast_offers)
    # אנחנו שולחים לו את הפורט שמצאנו הרגע
    # daemon=True: אומר שאם אני סוגרת את התוכנית הראשית, הטרד הזה ימות מיד
    t = threading.Thread(target=broadcast_offers, args=(server_port,), daemon=True)
    t.start()

    # 6. לולאת השוער (The Bouncer)
    # התוכנית הראשית נתקעת כאן ומחכה לאורחים
    while True:
        try:
            # accept() היא פעולה חוסמת! הקוד עוצר כאן.
            # הוא מתעורר רק כשמישהו דופק בדלת (מתחבר ב-TCP).
            client_sock, addr = server_tcp.accept()

            # הגיע לקוח!
            # אנחנו לא רוצים שהשוער ישחק איתו, כי אז השוער יהיה עסוק
            # ולא יוכל לפתוח את הדלת לאורחים נוספים.
            # לכן, אנחנו יוצרים טרד חדש (דילר) שיטפל בלקוח הזה.
            client_thread = threading.Thread(target=handle_client, args=(client_sock, addr))
            client_thread.start()

        except KeyboardInterrupt:
            # זה קורה אם את עושה Ctrl+C בטרמינל
            print("Server shutting down...")
            break
        except Exception as e:
            print(f"Server error: {e}")


if __name__ == "__main__":
    main()