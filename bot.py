import os
import sqlite3
from datetime import datetime
import telebot

# ======= تنظیمات =======
TOKEN = "8474488417:AAHCZtpqbbm3uW9SJvFBmhi4iF5CRKF8gCg"  # توکن واقعی بات
ADMIN_ID = 7016224361  # شناسه عددی تلگرام خودت
DB_PATH = "survey.db"
# ========================

bot = telebot.TeleBot(TOKEN)

# ---------- دیتابیس ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS surveys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        first_name TEXT,
        started_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        survey_id INTEGER,
        q_index INTEGER,
        question TEXT,
        answer TEXT,
        answered_at TEXT,
        FOREIGN KEY(survey_id) REFERENCES surveys(id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        user_id INTEGER PRIMARY KEY,
        survey_id INTEGER,
        current_q_index INTEGER
    )""")
    conn.commit()
    conn.close()

def create_survey_record(user):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO surveys(user_id, username, first_name, started_at) VALUES (?, ?, ?, ?)",
                (user.id, user.username or "", user.first_name or "", datetime.utcnow().isoformat()))
    survey_id = cur.lastrowid
    conn.commit()
    conn.close()
    return survey_id

def save_answer(survey_id, q_index, question, answer):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO answers(survey_id, q_index, question, answer, answered_at) VALUES (?, ?, ?, ?, ?)",
                (survey_id, q_index, question, answer, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def start_session(user_id, survey_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("REPLACE INTO sessions(user_id, survey_id, current_q_index) VALUES (?, ?, ?)",
                (user_id, survey_id, 0))
    conn.commit()
    conn.close()

def advance_session(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT current_q_index FROM sessions WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    cur_index = row[0] + 1
    cur.execute("UPDATE sessions SET current_q_index = ? WHERE user_id = ?", (cur_index, user_id))
    conn.commit()
    conn.close()
    return cur_index

def get_session(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT survey_id, current_q_index FROM sessions WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row if row else None

def end_session(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ---------- سوالات ----------
QUESTIONS = [
    "از لیدر کلن راضی هستید؟",
    "از کلن راضی هستید؟",
    "پیشنهاد و انتقادی دارید؟",
    "از گروه راضی هستید؟",
    "پیشنهاد یا انتقادی درباره گروه دارید؟"
]

# ---------- هندلرها ----------
@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    txt = (
        "سلام! این ربات نظرسنجی‌ست.\n\n"
        "دستورها:\n"
        "/survey — شروع نظرسنجی\n"
        "/quit — لغو نظرسنجی فعلی\n\n"
        "نظر شما برای ما خیلی مهمه، شروع کن با /survey"
    )
    bot.send_message(message.chat.id, txt)

@bot.message_handler(commands=['survey'])
def cmd_survey(message):
    user = message.from_user
    sess = get_session(user.id)
    if sess:
        bot.send_message(message.chat.id, "شما یک نظرسنجی باز دارید. برای لغو /quit بزنید.")
        return

    survey_id = create_survey_record(user)
    start_session(user.id, survey_id)
    first_q = QUESTIONS[0]
    bot.send_message(message.chat.id, f"سوال 1/{len(QUESTIONS)}:\n\n{first_q}")
    bot.send_message(ADMIN_ID, f"🔔 کاربر @{user.username or ''} (id: {user.id}) شروع به شرکت در نظرسنجی کرد.")

@bot.message_handler(commands=['quit'])
def cmd_quit(message):
    user = message.from_user
    if get_session(user.id):
        end_session(user.id)
        bot.reply_to(message, "نظرسنجی متوقف شد. اگر خواستی دوباره /survey بزن.")
    else:
        bot.reply_to(message, "جلسهٔ فعالی وجود ندارد.")

@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_text(message):
    user = message.from_user
    sess = get_session(user.id)
    if not sess:
        return

    survey_id, q_index = sess
    try:
        q_index_int = int(q_index)
    except:
        q_index_int = 0

    if q_index_int < 0 or q_index_int >= len(QUESTIONS):
        end_session(user.id)
        bot.send_message(message.chat.id, "خطا در جلسهٔ نظرسنجی — جلسه پایان یافت.")
        return

    question_text = QUESTIONS[q_index_int]
    answer_text = message.text.strip()

    save_answer(survey_id, q_index_int, question_text, answer_text)

    # ارسال به ادمین
    admin_msg = (
        f"📥 پاسخ جدید از @{user.username or ''} (id: {user.id}):\n"
        f"سوال {q_index_int+1}/{len(QUESTIONS)}:\n{question_text}\n\n"
        f"📝 جواب:\n{answer_text}\n\n"
        f"⏰ زمان (UTC): {datetime.utcnow().isoformat()}"
    )
    try:
        bot.send_message(ADMIN_ID, admin_msg)
    except Exception as e:
        print("Error sending to admin:", e)

    # ✅ پیام تأیید برای کاربر
    bot.send_message(message.chat.id, "✅ جوابت ارسال شد.")

    # رفتن به سوال بعدی یا پایان
    next_index = advance_session(user.id)
    if next_index is None:
        end_session(user.id)
        bot.send_message(message.chat.id, "خطا در ادامهٔ نظرسنجی. لطفاً بعداً تلاش کن.")
        return

    if next_index >= len(QUESTIONS):
        end_session(user.id)
        bot.send_message(message.chat.id, "ممنون! نظرسنجی تمام شد. پاسخ‌هایت ثبت و برای ادمین ارسال شد 🙏")
        bot.send_message(ADMIN_ID, f"✅ کاربر @{user.username or ''} (id: {user.id}) نظرسنجی را تمام کرد.")
    else:
        next_q = QUESTIONS[next_index]
        bot.send_message(message.chat.id, f"سوال {next_index+1}/{len(QUESTIONS)}:\n\n{next_q}")

# /export — فقط برای ادمین: خروجی CSV از همهٔ پاسخ‌ها
@bot.message_handler(commands=['export'])
def cmd_export(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "دسترسی ندارید.")
        return

    import csv
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.user_id, s.username, s.first_name, a.q_index, a.question, a.answer, a.answered_at
        FROM surveys s
        JOIN answers a ON s.id = a.survey_id
        ORDER BY s.id, a.q_index
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        bot.send_message(ADMIN_ID, "هیچ پاسخی ثبت نشده.")
        return

    csv_path = "survey_export.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["survey_id", "user_id", "username", "first_name", "q_index", "question", "answer", "answered_at"])
        writer.writerows(rows)

    with open(csv_path, "rb") as f:
        bot.send_document(ADMIN_ID, f)

# ---------- init ----------
if __name__ == "__main__":
    init_db()
    print("Survey bot started...")
    bot.infinity_polling()