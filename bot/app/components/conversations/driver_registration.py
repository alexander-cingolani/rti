"""
This module contains all the callbacks necessary to register drivers to the database.
"""

import os
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLASession
from sqlalchemy.orm import sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from models import Driver
from queries import (
    fetch_driver_by_psn_id,
    fetch_driver_by_telegram_id,
    fetch_similar_driver,
)

CHECK_ID, ID = range(2)


engine = create_engine(os.environ["DB_URL"])

DBSession = sessionmaker(bind=engine, autoflush=False)


async def driver_registration_entry_point(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Asks the user for his PSN ID"""

    session = DBSession()
    user = update.effective_user
    user_data = cast(dict[str, Any], context.user_data)
    user_data["sqla_session"] = session

    driver = fetch_driver_by_telegram_id(session, str(user.id))
    if not driver:
        text = "Per registrarti, scrivimi il tuo <i>PSN ID</i>:"
        await update.message.reply_text(text)
    else:
        text = f"Sei già registrato/a come <code>{driver.psn_id}</code>, sei tu?"
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Sì, sono io.", callback_data="correct_id"),
                    InlineKeyboardButton("No, non sono io.", callback_data="change_id"),
                ],
            ]
        )
        user_data["driver_obj"] = driver
        await update.message.reply_text(text=text, reply_markup=reply_markup)
    return CHECK_ID


async def check_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Checks if the given psn_id is correct and saves the user's telegram_id if an exact
    match is found. If no exact match is found the bot provides the user with a similar
    ID and asks if that is the right one.
    """
    user_data = cast(dict[str, Any], context.user_data)
    sqla_session: SQLASession = user_data["sqla_session"]
    if getattr(update.callback_query, "data", ""):
        if update.callback_query.data == "change_id":
            driver: Driver = user_data["driver_obj"]
            driver.telegram_id = None
            sqla_session.commit()
            text = "Scrivimi il tuo <i>ID PSN</i>:"
            await update.callback_query.edit_message_text(text)
            return CHECK_ID

        if update.callback_query.data == "correct_id":
            await update.callback_query.edit_message_text("👌")
            sqla_session.close()
            user_data.clear()
            return ConversationHandler.END

    driver_obj = fetch_driver_by_psn_id(sqla_session, update.message.text)
    if driver_obj:
        # Checks that no other user is registered to the requested psn_id
        if driver_obj.telegram_id:
            text = (
                "Oh oh.\nSembra che qualcuno si sia già registrato con questo ID.\n"
                f"Se credi sia un errore, contatta un amministratore per risolvere il problema."
            )
        else:
            driver_obj.telegram_id = update.effective_user.id
            sqla_session.commit()
            text = (
                "Ok!\n"
                "Dopo le tue prime gare in RTI, sarai in grado di usare il comando /stats per "
                "dare un'occhiata alle tue statistiche."
            )
        await update.message.reply_text(text)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    if suggested_driver := fetch_similar_driver(
        sqla_session, psn_id=update.message.text
    ):
        if not suggested_driver.telegram_id:
            user_data["suggested_driver"] = suggested_driver.psn_id
            text = f'Ho trovato un ID simile: "<code>{suggested_driver.psn_id}</code>", sei tu?'
            reply_markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Sì", callback_data="y"),
                        InlineKeyboardButton("No", callback_data="n"),
                    ]
                ]
            )
            await update.message.reply_text(text=text, reply_markup=reply_markup)
            return ID

        if suggested_driver.telegram_id == update.effective_user.id:
            text = f"Sei già registrato con <code>{suggested_driver.psn_id}</code>.\n"
            await update.message.reply_text(text)
            sqla_session.close()
            user_data.clear()
            return ConversationHandler.END

    text = "Non ho trovato un ID corrispondente, riprova perfavore:"
    await update.message.reply_text(text=text)
    return CHECK_ID


async def verify_correction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """This callback is activated when the previous callback (check_id) didn't find an
    exact match to the ID provided by the user, in which case it gave the option to select
    a similar ID. This callback therefore handles the user's choice (if to accept the option
    or not)."""

    user_data = cast(dict[str, Any], context.user_data)
    sqla_session: SQLASession = user_data["sqla_session"]

    if update.callback_query.data == "y":
        driver = cast(
            Driver,
            fetch_driver_by_psn_id(sqla_session, psn_id=user_data["suggested_driver"]),
        )
        if driver.telegram_id and driver.telegram_id != update.effective_user.id:
            text = (
                "Oh oh. Sembra che qualcuno si sia già registrato con questo ID."
                f"Se sei sicuro che {user_data['suggested_driver']} sia il tuo ID, "
                f"contatta un amministratore."
            )
            sqla_session.close()
            user_data.clear()
            return ConversationHandler.END

        driver.telegram_id = update.effective_user.id
        sqla_session.commit()
        text = (
            "Perfetto!\n"
            "Ora hai accesso ai comandi /classifica, /ultima_gara e /my_stats.\n"
        )
        await update.callback_query.edit_message_text(text)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    text = (
        "Ok, se vuoi riprova digitando l'ID PSN, altrimenti /annulla."
        "potrebbe darsi che il tuo ID non sia stato ancora aggiunto nel nostro database"
        " in questo caso prova a contattare un amministratore per fartelo aggiungere."
    )
    await update.callback_query.edit_message_text(text)
    return CHECK_ID


async def cancel_registration(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """This callback is activated when the user decides to cancel the registration."""

    await update.message.reply_text("👌")
    user_data = cast(dict[str, Any], context.user_data)
    cast(SQLASession, user_data["sqla_session"]).close()
    user_data.clear()
    return ConversationHandler.END


async def invalid_psn_id(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    """This callback is activated when the user inputs an invalid psn_id,
    telling him to try again."""

    await update.message.reply_text("L'ID PlayStation inserito non è valido, riprova:")
    return CHECK_ID


async def wrong_chat(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    """Tells the user to use the /registrami command in the private chat."""
    text = (
        "Questo comando è disponibile solamente in chat privata. "
        "Clicca sulla mia immagine del profilo per accedervi."
    )
    await update.message.reply_text(text)
    return ConversationHandler.END


driver_registration = ConversationHandler(
    entry_points=[
        CommandHandler(
            "registrami", driver_registration_entry_point, filters.ChatType.PRIVATE
        ),
        CommandHandler("registrami", wrong_chat, filters.ChatType.GROUPS),
    ],
    states={
        CHECK_ID: [
            MessageHandler(filters.Regex(r"^[A-Za-z][A-Za-z0-9-_]{2,15}$"), check_id),
            CallbackQueryHandler(check_id, r"incorrect_id|correct_id|change_id"),
        ],
        ID: [CallbackQueryHandler(verify_correction, r"y|n")],
    },
    fallbacks=[
        CommandHandler("annulla", cancel_registration),
        CommandHandler("registrami", driver_registration_entry_point),
        MessageHandler(filters.TEXT, invalid_psn_id),
    ],
    allow_reentry=True,
)
