import kb
import config
import asyncio
import db_functions
import text
import os
import Admin
import re


from math import ceil
from time import sleep
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import CallbackQuery, Message, ContentType, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command, Filter, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession


# session = AiohttpSession(proxy='http://proxy.server:3128')
# bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


class OrderAdd(StatesGroup):
    # folder_name = State()
    folder_mode = State()

    new_vertices = State()
    new_group_vertices = State()
    create_group_vertex = State()
    add_group_folder = State()

    set_head_text = State()


async def clear_chat(chat_id: int, message_id: int) -> None:
    try:
        for i in range(message_id, 0, -1):
            await bot.delete_message(chat_id, i)

    except TelegramBadRequest as ex:
        pass


async def check_user_in_table(message: Message, chat_id: int) -> None:
    if not db_functions.is_user_in_table(chat_id):
        db_functions.create_user(chat_id)
        if message.chat.type == "private":
            await message.answer(text=text.new_chat_message)


async def send_start_message(level_message_type: str,
                             message: Message | None = None,
                             callback: CallbackQuery | None = None,
                             change_page: int | None = 0):
    
    if level_message_type == "message":
        chat_type = message.chat.type
        chat_id = message.chat.id
    else:
        chat_type = callback.message.chat.type
        chat_id = callback.message.chat.id

    folder_type, vertex_id = db_functions.get_value_db("Users", "path", chat_id).split("\\")[-1].split(":")
    delete_mode = db_functions.get_value_db("Users", "delete_mode", chat_id)
    vertex_id = int(vertex_id)
    private_mode = db_functions.get_value_db("Folders", "private_mode", vertex_id)

    param = db_functions.get_full_parameters(vertex_id)
    next_vertices = [] if param[3].split(";")[0] == "" else  param[3].split(";")


    pages = [int(page) for page in db_functions.get_value_db("Users", "pages", chat_id).split("\\")]
    if change_page != 0:
        pages[-1] += change_page
        db_functions.set_value_db("Users", "pages", chat_id, "\\".join([str(page) for page in pages]))
    if len(next_vertices) == 0:
        db_functions.set_value_db("Users", "delete_mode", chat_id, 0)

    print(vertex_id, param)
    text_message=text.start_text( chat_type=chat_type,
                                folder_link=config.encoding_folder(f"{folder_type}:{vertex_id}", param[0]),
                                folder_name=param[0],
                                private_mode=param[2],
                                delete_mode=delete_mode,
                                is_empty=(len(next_vertices) == 0),
                                head_text=param[4]
    )
    reply_markup=kb.inline_start_kb(chat_id=chat_id,
                                autor_id=param[1],
                                chat_type=chat_type,
                                folder_type=folder_type,
                                private_mode=private_mode,
                                delete_mode=delete_mode,
                                next_vertices=next_vertices
    )


    if level_message_type == "message":
        await message.answer(text=text_message, reply_markup=reply_markup)
    else:
        await callback.message.edit_text(text=text_message, reply_markup=reply_markup)


    if level_message_type == "message" and chat_type == "private":
        await clear_chat(chat_id, message.message_id)





@dp.message(CommandStart())
async def start(message: Message):

    chat_id = message.chat.id

    await check_user_in_table(message, chat_id)


    if message.chat.type != "private":
        row_id = int(db_functions.get_value_db("Users", "path", chat_id).split(":")[-1])
        next_vertices_string = db_functions.get_value_db("Folders", "next_vertices", row_id)
        if next_vertices_string == "":
            await message.answer(text=text.add_group_folder_text, reply_markup=kb.inline_add_group_kb())
            return

    await send_start_message(level_message_type="message", message=message)


@dp.message(Command('help'))
async def help(message: Message):
    await message.answer(text=text.help_instruction)


@dp.message(Command('group_folder'))
async def group_folder(message: Message):
    if message.chat.type == "private":
        await message.answer(text=text.add_group_folder_instruction, reply_markup=kb.inline_create_group_kb())


@dp.message(Command('made_by'))
async def made_by(message: Message):
    await message.answer(text=text.made_by_text)




@dp.callback_query(F.data)
async def inline_callback(callback: CallbackQuery, state: FSMContext):
    
    await state.clear()
    chat_type = callback.message.chat.type
    chat_id = callback.message.chat.id
    call = str(callback.data)


    vertex_id = int(db_functions.get_value_db("Users", "path", chat_id).split("\\")[-1].split(":")[-1])
    private_mode = db_functions.get_value_db("Folders", "private_mode", vertex_id)
    next_vertices = db_functions.get_value_db("Folders", "next_vertices", vertex_id).split(";")
    next_vertices = [] if next_vertices[0] == "" else  next_vertices
    page = int(db_functions.get_value_db("Users", "pages", chat_id).split("\\")[-1])
    cnt_page = ceil(len(next_vertices) / 10)

    root_folder_type = ...
    

    match call:

        case 'head':
            await callback.answer()

            await callback.message.answer(text=text.add_head_text, reply_markup=kb.reply_head_text_kb())
            
            await state.set_state(OrderAdd.set_head_text)
            await state.update_data(autor=callback.from_user.id)
            
        case 'add':
            await callback.answer()
            await state.set_state(OrderAdd.new_vertices)
            await state.update_data(cnt=1)
            await callback.message.answer(text=text.add_vertex_text, reply_markup=kb.reply_media_group_kb())

            if chat_type != "private" or private_mode == 2:
                await state.update_data(for_what="group")
            else:
                await state.update_data(for_what="bot")

        case 'delete':
            await callback.answer()

            db_functions.set_value_db("Users", "delete_mode", chat_id, 1)

            await send_start_message(level_message_type="callback", callback=callback)

        case 'delete_back':
            await callback.answer()

            db_functions.set_value_db("Users", "delete_mode", chat_id, 0)

            await send_start_message(level_message_type="callback", callback=callback)

        case 'pagina_back':
            if page == 1:
                await callback.answer(text=text.first_page_answer)

            else:
                await callback.answer()
                await send_start_message(level_message_type="callback", callback=callback, change_page=-1)
                
        case 'pagina_view':
            await callback.answer(text=text.now_page_answer(page, cnt_page))

        case 'pagina_next':
            if page == cnt_page:
                await callback.answer(text=text.last_page_answer)

            else:
                await callback.answer()
                await send_start_message(level_message_type="callback", callback=callback, change_page=1)

        case "back":
            await callback.answer()

            path = db_functions.get_value_db("Users", "path", chat_id).split("\\")
            pages = db_functions.get_value_db("Users", "pages", chat_id).split("\\")
            path.pop()
            pages.pop()
            db_functions.set_value_db("Users", "path", chat_id, "\\".join(path))
            db_functions.set_value_db("Users", "pages", chat_id, "\\".join(pages))

            await send_start_message(level_message_type="callback", callback=callback)

        case "group_folder":
            await callback.answer()

            await callback.message.answer(text=text.create_group_folder_instruction)
            await state.set_state(OrderAdd.new_vertices)
            await state.update_data(for_what="group")

        case _:
            await callback.answer()

            vertex_type, vertex_id = call.split(":")
            vertex_id = int(vertex_id)
            delete_mode = db_functions.get_value_db("Users", "delete_mode", chat_id)
            

            if delete_mode:
                try:
                    db_functions.delete(chat_id, call)
                except:
                    await send_start_message(level_message_type="callback", callback=callback)
                else:
                    await send_start_message(level_message_type="callback", callback=callback)
                return
            
            if vertex_type == "F":
                try:
                    test = db_functions.get_value_db("Folders", "id", vertex_id)
                except:
                    pass
                else:
                    path = db_functions.get_value_db("Users", "path", chat_id).split("\\")
                    pages = db_functions.get_value_db("Users", "pages", chat_id).split("\\")
                    path.append(call)
                    pages.append("1")
                    db_functions.set_value_db("Users", "path", chat_id, "\\".join(path))
                    db_functions.set_value_db("Users", "pages", chat_id, "\\".join(pages))
    
                await send_start_message(level_message_type="callback", callback=callback)

            else:
                try:
                    file_type = db_functions.get_value_db("Files", "file_type", vertex_id)
                    file_id = db_functions.get_value_db("Files", "file_id", vertex_id)
                except:
                    await send_start_message(level_message_type="callback", callback=callback)
                else:
                    match file_type:

                        case "photo":
                            await bot.send_photo(chat_id=callback.message.chat.id, photo=file_id)
                        case "video":
                            await bot.send_video(chat_id=callback.message.chat.id, video=file_id)
                        case "document":
                            await bot.send_document(chat_id=callback.message.chat.id, document=file_id)
                        case "audio":
                            await bot.send_audio(chat_id=callback.message.chat.id, audio=file_id)
                        case "voice":
                            await bot.send_voice(chat_id=callback.message.chat.id, voice=file_id)
                        case "sticker":
                            await bot.send_sticker(chat_id=callback.message.chat.id, sticker=file_id)
                        case "video_note":
                            await bot.send_video_note(chat_id=callback.message.chat.id, video_note=file_id)
                        case _:
                            await callback.message.answer(text="Произошла ошибка в отправке файла.")




@dp.message(F.text.regexp(config.REGEX), OrderAdd.new_vertices)
async def regex_link_add_private(message: Message, state: FSMContext):
    
    chat_id = message.chat.id
    decode = config.decoding_folder(message.text)
    new_vertex_id = int(decode[0].split(":")[-1])
    user_data = await state.get_data()


    if user_data["for_what"] == "group":

        if db_functions.is_folder_good(new_vertex_id):
            # row_id = int(db_functions.get_value_db("Users", "path", chat_id).split(":")[-1])
            db_functions.add_folder(chat_id, new_vertex_id)
        else:
            await message.answer("Эту папку нельзя добавить")

    if user_data["for_what"] == "bot":
        try:
            db_functions.add_folder(chat_id, new_vertex_id)
        except TypeError:
            await message.answer(text=text.link_is_not_valid_error)
        except KeyError as ex:
            if ex == "You cannot add a private folder":
                await message.answer(text=text.private_folder_error)
            else:
                await message.answer(text=text.doublicate_folder_error)
        else:
            await message.answer(f"Добавлена папка: {decode[-1]}")


    await state.clear()
    await send_start_message(level_message_type="message", message=message)


@dp.message(F.text, OrderAdd.new_vertices)
async def folder_name_chosen(message: Message, state: FSMContext):

    chat_id = message.chat.id
    user_data = await state.get_data()
    
    
    if message.text == "Завершить добавление":
        await state.clear()
        await send_start_message(level_message_type="message", message=message)
        return
    
    if user_data["for_what"] == "group":
        try:
            print(chat_id, user_data)
            db_functions.create(chat_id, "fold", message.text, 2)
            print("yes")
        except:
            await message.answer(text=text.long_name_error)
        else:
            await message.answer(text=text.folder_is_create_text(message.text.lower(), message.text))

        await state.clear()
        await send_start_message(level_message_type="message", message=message)
    
    else:
        await state.update_data(folder_name=message.text)
        await message.answer(text.choose_name_text, reply_markup=kb.reply_choose_private_kb())

    await state.set_state(OrderAdd.folder_mode)


@dp.message(F.text, OrderAdd.folder_mode)
async def private_chosen(message: Message, state: FSMContext):

    user_data = await state.get_data()
    chat_id = message.chat.id

    if message.text in ['Приватная', 'Публичная']:
        private_mode = 1 if message.text.lower() == 'приватная' else 0
        try:
            db_functions.create(chat_id,  "fold", user_data['folder_name'], private_mode)
        except:
            await message.answer(text=text.long_name_error)
        else:
            await message.answer(text=text.folder_is_create_text(message.text.lower(), user_data['folder_name']))
    
    else:
        await message.answer(text=text.incorrectly_private_chosen_error, reply_markup=kb.reply_choose_private_kb())


    await state.clear()
    await send_start_message(level_message_type="message", message=message)


@dp.message(OrderAdd.new_vertices)
async def send_media(message: Message, state: FSMContext):

    user_id = message.chat.id
    user_data = await state.get_data()
    cnt = user_data["cnt"]


    if message.text == "Завершить добавление":
        await state.clear()
        await send_start_message(level_message_type="message", message=message)
        return

    if message.photo:
        media = [message.photo[2].file_id, f"photo_{cnt}", "photo"]
    elif message.video:
        media = [message.video.file_id, message.video.file_name, "video"]
    elif message.document:
        media = [message.document.file_id, message.document.file_name, "document"]
    elif message.audio:
        media = [message.audio.file_id, message.audio.file_name, "audio"]
    elif message.voice:
        media = [message.voice.file_id, f"voice_{cnt}", "voice"]
    elif message.sticker:
        media = [message.sticker.file_id, f"sticker_{cnt}", "sticker"]
    elif message.video_note:
        media = [message.video_note.file_id, f"video_note_{cnt}", "video_note"]
    else:
        await message.answer(text=text.incorrectly_media_error)
        return
    

    db_functions.create(user_id, "file", media[1], file_id=media[0], file_type=media[2])
    

    await state.update_data(cnt=cnt + 1)
    await message.answer(text=f"{cnt} медиа добавлено")


@dp.message(F.text, OrderAdd.set_head_text)
async def set_heat_text(message: Message, state: FSMContext):

    chat_id = message.chat.id
    vertex_id = int(db_functions.get_value_db("Users", "path", chat_id).split("\\")[-1].split(":")[-1])

    if message.text == "Очистить текст":
        db_functions.set_value_db("Folders", "head_text", vertex_id, "")

    else:
        db_functions.set_value_db("Folders", "head_text", vertex_id, message.text)
        await message.answer(text=text.complete_head_text)

    await state.clear()
    await send_start_message(level_message_type="message", message=message)




@dp.message(F.text)
async def other_text(message: Message, state: FSMContext):
    chat_type = message.chat.type
    if chat_type == "private":
        await message.answer(text=text.incorrectly_text_error)


    

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    # os.remove("database.db")
    # Admin.create_db()
    asyncio.run(main())