import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import sqlite3
from datetime import datetime

# === НАСТРОЙКИ === ЗАМЕНИТЕ ЭТИ ДАННЫЕ ===
TOKEN = "7854171673:AAEQs0acB0pfD0KMvhqH3gKFop1L8vZee-A"
ADMIN_CHAT_ID = 123456789  # Замените на ваш ID из @userinfobot
# === КОНЕЦ НАСТРОЕК ===

# Этапы разговора
FREQUENCY, DURATION = range(2)

# Вопросы теста
QUESTIONS = [
    {"text": "испытывали полную апатию, прострацию и безучастность?", "zone": "burnout"},
    {"text": "не могли заставить себя выполнить даже простые рутинные действия?", "zone": "burnout"},
    {"text": "ощущали, что краски жизни поблекли, а то, что раньше зажигало, больше не вызывает энтузиазм?", "zone": "burnout"},
    {"text": "оставляли без внимания важные для вас задачи, пренебрегали ими?", "zone": "burnout"},
    {"text": "ощущали полную расслабленность и глубокое удовлетворение?", "zone": "integration"},
    {"text": "спокойно наблюдали за происходящим без необходимости действовать?", "zone": "integration"},
    {"text": "ощущали радость и спокойствие одновременно?", "zone": "integration"},
    {"text": "действовали сфокусировано, но без напряжения или возбуждения?", "zone": "integration"},
    {"text": "ощущали приятное возбуждение и/или предвкушение?", "zone": "integration"},
    {"text": "проявляли активный интерес и с энтузиазмом действовали?", "zone": "integration"},
    {"text": "испытывали перевозбуждение, повышенную чувствительность даже к нейтральным стимулам?", "zone": "distress"},
    {"text": "раздражались и тревожились даже от мелочей?", "zone": "distress"},
    {"text": "чувствовали неуправляемую панику, парализующий страх или гнев?", "zone": "distress"},
    {"text": "не могли контролировать свои слова и действия из-за эмоционального перевозбуждения?", "zone": "distress"},
]

# Настройки ответов
FREQUENCY_SCORES = {"Ни разу": 0, "Несколько раз": 2, "Более половины дней": 5, "Почти каждый день": 10}
DURATION_MULTIPLIERS = {"Несколько минут": 0.1, "Несколько часов": 3, "Сутки и более": 10}

# База данных
def init_db():
    conn = sqlite3.connect('neurobalance.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, username TEXT, timestamp TEXT,
                burnout_percent REAL, integration_percent REAL, distress_percent REAL)''')
    conn.commit()
    conn.close()

def save_test_result(user_id, username, burnout_percent, integration_percent, distress_percent):
    from datetime import datetime
    conn = sqlite3.connect('neurobalance.db')
    cur = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute('''INSERT INTO test_results (user_id, username, timestamp, burnout_percent, integration_percent, distress_percent) 
                VALUES (?, ?, ?, ?, ?, ?)''',
                (user_id, username, timestamp, burnout_percent, integration_percent, distress_percent))
    conn.commit()
    conn.close()

# Логика бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    context.user_data['answers'] = []
    context.user_data['current_question'] = 0
    context.user_data['user_id'] = user.id
    context.user_data['username'] = user.username or user.first_name
    context.user_data['last_message_id'] = None
    
    message = await send_question(update, context, 0)
    context.user_data['last_message_id'] = message.message_id
    return FREQUENCY

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question_index):
    question_text = QUESTIONS[question_index]['text']
    progress = f"({question_index + 1}/{len(QUESTIONS)})"
    text = f"🧠 Вопрос {progress}:\nКак часто за последние 2 недели вы:\n{question_text}"
    
    keyboard = [["Ни разу", "Несколько раз"], ["Более половины дней", "Почти каждый день"], ["⏪ Назад", "🔄 Сбросить"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    if context.user_data.get('last_message_id'):
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data['last_message_id'])
        except: pass
    
    message = await update.message.reply_text(text, reply_markup=reply_markup)
    return message

async def handle_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_answer = update.message.text
    current_question = context.user_data['current_question']
    
    if user_answer == "🔄 Сбросить": return await reset_test(update, context)
    if user_answer == "⏪ Назад": return await go_back(update, context)
    
    context.user_data['current_frequency'] = user_answer
    context.user_data['current_frequency_score'] = FREQUENCY_SCORES[user_answer]
    
    try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except: pass
    
    if user_answer == "Ни разу":
        context.user_data['answers'].append({'question': current_question, 'frequency': user_answer, 'frequency_score': 0, 'duration': 'Не задано', 'final_score': 0, 'zone': QUESTIONS[current_question]['zone']})
        return await next_question(update, context)
    
    question_text = QUESTIONS[current_question]['text']
    text = f"🧠 Вопрос ({current_question + 1}/{len(QUESTIONS)}):\nКак часто за последние 2 недели вы:\n{question_text}\n\n📅 Ответ: {user_answer}\n\n⏱ Теперь укажите длительность:"
    keyboard = [["Несколько минут", "Несколько часов", "Сутки и более"], ["⏪ Назад", "🔄 Сбросить"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=context.user_data['last_message_id'], text=text, reply_markup=reply_markup)
    return DURATION

async def handle_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_answer = update.message.text
    current_question = context.user_data['current_question']
    
    if user_answer == "🔄 Сбросить": return await reset_test(update, context)
    if user_answer == "⏪ Назад":
        context.user_data['current_question'] = current_question
        message = await send_question(update, context, current_question)
        context.user_data['last_message_id'] = message.message_id
        return FREQUENCY
    
    try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except: pass
    
    frequency_score = context.user_data['current_frequency_score']
    duration_multiplier = DURATION_MULTIPLIERS[user_answer]
    final_score = frequency_score * duration_multiplier
    
    context.user_data['answers'].append({
        'question': current_question, 'frequency': context.user_data['current_frequency'],
        'frequency_score': frequency_score, 'duration': user_answer,
        'final_score': final_score, 'zone': QUESTIONS[current_question]['zone']
    })
    
    return await next_question(update, context)

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['current_question'] += 1
    current_question = context.user_data['current_question']
    
    if current_question < len(QUESTIONS):
        message = await send_question(update, context, current_question)
        context.user_data['last_message_id'] = message.message_id
        return FREQUENCY
    else:
        return await calculate_results(update, context)

async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_question = context.user_data['current_question']
    if current_question > 0:
        if context.user_data['answers']: context.user_data['answers'].pop()
        context.user_data['current_question'] -= 1
        previous_question = context.user_data['current_question']
        message = await send_question(update, context, previous_question)
        context.user_data['last_message_id'] = message.message_id
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
        except: pass
        return FREQUENCY
    else:
        message = await send_question(update, context, current_question)
        context.user_data['last_message_id'] = message.message_id
        return FREQUENCY

async def reset_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data['last_message_id'])
    except: pass
    try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except: pass
    return await start(update, context)

async def calculate_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answers = context.user_data['answers']
    zone_scores = {'burnout': 0, 'integration': 0, 'distress': 0}
    
    for answer in answers:
        zone = answer['zone']
        zone_scores[zone] += answer['final_score']
    
    total_score = sum(zone_scores.values())
    
    if total_score > 0:
        burnout_percent = round((zone_scores['burnout'] / total_score) * 100, 1)
        integration_percent = round((zone_scores['integration'] / total_score) * 100, 1)
        distress_percent = round((zone_scores['distress'] / total_score) * 100, 1)
    else:
        burnout_percent = integration_percent = distress_percent = 0
    
    save_test_result(
        user_id=context.user_data['user_id'],
        username=context.user_data['username'],
        burnout_percent=burnout_percent,
        integration_percent=integration_percent,
        distress_percent=distress_percent
    )
    
    admin_message = f"📊 Новый результат!\nПользователь: @{context.user_data['username']}\nВыгорание: {burnout_percent}%\nИнтеграция: {integration_percent}%\nДистресс: {distress_percent}%"
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message)
    
    result_text = f"🎯 ВАШИ РЕЗУЛЬТАТЫ:\n\n🟣 Зона выгорания: {burnout_percent}%\n🟢 Зона интеграции: {integration_percent}%\n🔴 Зона дистресса: {distress_percent}%\n\nСпасибо за прохождение теста! Для расшифровки напишите мне в Instagram\n\nЧтобы пройти заново, напишите /start"
    
    try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data['last_message_id'])
    except: pass
    
    await update.message.reply_text(result_text, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_frequency)],
            DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_duration)],
        }, fallbacks=[])
    application.add_handler(conv_handler)
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
