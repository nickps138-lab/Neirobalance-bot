import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройки из переменных окружения
TOKEN = os.environ['TOKEN']
ADMIN_CHAT_ID = int(os.environ['ADMIN_CHAT_ID'])

# Включим логирование
logging.basicConfig(level=logging.INFO)

# Этапы разговора
FREQUENCY, DURATION = range(2)

# Вопросы теста
QUESTIONS = [
    "испытывали полную апатию, прострацию и безучастность?",
    "не могли заставить себя выполнить даже простые рутинные действия?",
    "ощущали, что краски жизни поблекли, а то, что раньше зажигало, больше не вызывает энтузиазм?",
    "оставляли без внимания важные для вас задачи, пренебрегали ими?",
    "ощущали полную расслабленность и глубокое удовлетворение?",
    "спокойно наблюдали за происходящим без необходимости действовать?",
    "ощущали радость и спокойствие одновременно?",
    "действовали сфокусировано, но без напряжения или возбуждения?",
    "ощущали приятное возбуждение и/или предвкушение?",
    "проявляли активный интерес и с энтузиазмом действовали?",
    "испытывали перевозбуждение, повышенную чувствительность даже к нейтральным стимулам?",
    "раздражались и тревожились даже от мелочей?",
    "чувствовали неуправляемую панику, парализующий страх или гнев?",
    "не могли контролировать свои слова и действия из-за эмоционального перевозбуждения?"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    context.user_data['answers'] = []
    context.user_data['current_question'] = 0
    
    await update.message.reply_text(
        "👋 Добро пожаловать в тест на НейроБаланс!\n\n"
        "Ответьте на 14 вопросов о вашем состоянии за последние 2 недели.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await send_question(update, context)
    return FREQUENCY

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question_index = context.user_data['current_question']
    question_text = QUESTIONS[question_index]
    
    text = f"❓ Вопрос {question_index + 1}/14:\n{question_text}"
    
    keyboard = [
        ["Ни разу", "Несколько раз"],
        ["Более половины дней", "Почти каждый день"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text
    question_index = context.user_data['current_question']
    
    # Простая логика подсчета
    scores = {"Ни разу": 0, "Несколько раз": 2, "Более половины дней": 5, "Почти каждый день": 10}
    score = scores.get(answer, 0)
    
    context.user_data['answers'].append(score)
    context.user_data['current_question'] += 1
    
    if context.user_data['current_question'] < len(QUESTIONS):
        await send_question(update, context)
        return FREQUENCY
    else:
        return await show_results(update, context)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scores = context.user_data['answers']
    total = sum(scores)
    
    # Простой расчет процентов
    burnout = sum(scores[0:4]) / total * 100 if total > 0 else 0
    integration = sum(scores[4:10]) / total * 100 if total > 0 else 0
    distress = sum(scores[10:14]) / total * 100 if total > 0 else 0
    
    result_text = f"""🎯 РЕЗУЛЬТАТЫ ТЕСТА:

🟣 Выгорание: {burnout:.1f}%
🟢 Интеграция: {integration:.1f}%
🔴 Дистресс: {distress:.1f}%

💡 Для консультации напишите в Instagram"""

    await update.message.reply_text(
        result_text,
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Уведомление админу
    user = update.message.from_user
    await context.bot.send_message(
        ADMIN_CHAT_ID,
        f"📊 Новый результат!\n"
        f"Пользователь: {user.first_name}\n"
        f"Выгорание: {burnout:.1f}%\n"
        f"Интеграция: {integration:.1f}%\n"
        f"Дистресс: {distress:.1f}%"
    )
    
    return ConversationHandler.END

def main():
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer)]
        },
        fallbacks=[]
    )
    
    application.add_handler(conv_handler)
    
    print("✅ Бот запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
