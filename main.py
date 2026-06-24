import asyncio
import sqlite3
import re
import requests
import os
from bs4 import BeautifulSoup
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

ChannelUsername = "@ORSHAGAK"

Url = "https://ogak.by/расписание-учебных-занятий/"

DbPath = os.path.join(
    os.path.dirname(__file__),
    "Data",
    "TgBotDB.db"
)

bot = Bot(
    token="8939395956:AAEOYkHKCiRIYaVZXEYpWHArij9-SHyfmuA"
)

dp = Dispatcher()
userStates = {}


@dataclass
class ScheduleRecord:
    GroupNumber: int
    LessonNumber: int
    SubjectName: str = ""
    RawTeachers: str = ""
    Classroom: str = ""


def FormatNumber(number):
    if number >= 10 and number <= 99:
        str_number = str(number)

        return str_number[0] + "—" + str_number[1]

    return str(number)


def Normalize(text):
    if text is None:
        text = ""

    text = BeautifulSoup(
        text,
        "html.parser"
    ).get_text()

    text = (
        text
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )

    if text == "":
        return "-"

    return text


def ExtractDigits(value):
    return "".join(
        x for x in value
        if x.isdigit()
    )


async def ParseScheduleAsync():
    headers = {
        "User-Agent":
            "Mozilla/5.0"
    }

    response = requests.get(
        Url,
        headers=headers
    )

    html = response.text

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    scheduleDate = ParseScheduleDate(
        soup
    )

    with open(
            "date.txt",
            "w",
            encoding="utf-8"
    ) as file:

        file.write(scheduleDate)

    result = []
    table = soup.select_one(
        "table.wpdtSimpleTable"
    )

    if table is None:
        return result

    rows = table.find_all("tr")
    currentGroup = 0
    currentLesson = 0

    for row in rows:

        cells = row.find_all("td")

        if not cells:
            continue

        values = [
            Normalize(
                x.text
            )
            for x in cells
        ]

        if any(
                "№ группы" in x
                for x in values
        ):
            continue

        if any(
                "Учебный предмет" in x
                for x in values
        ):
            continue
        rowData = {}
        for cell in cells:
            index = cell.get(
                "data-col-index",
                "-1"
            )
            rowData[int(index)] = Normalize(
                cell.text
            )
        if 0 in rowData:
            try:
                currentGroup = int(
                    ExtractDigits(
                        rowData[0]
                    )
                )
            except:
                pass
        if 1 in rowData:
            try:
                currentLesson = int(
                    ExtractDigits(
                        rowData[1]
                    )
                )
            except:
                pass
        subject = rowData.get(
            2,
            "-"
        )

        classroom = rowData.get(
            3,
            "-"
        )

        teacher = rowData.get(
            4,
            "-"
        )

        if (
                subject == "-"
                and classroom == "-"
                and teacher == "-"
        ):
            continue

        result.append(
            ScheduleRecord(
                GroupNumber=currentGroup,
                LessonNumber=currentLesson,
                SubjectName=subject,
                RawTeachers=teacher,
                Classroom=classroom
            )
        )
    return result


def SaveToDatabase(records):
    connection = sqlite3.connect(
        DbPath
    )
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM Schedule"
    )
    cursor.execute(
        "DELETE FROM sqlite_sequence WHERE name='Schedule'"
    )

    for item in records:
        cursor.execute(
            """
            INSERT INTO Schedule
            (
            GroupNumber,
            LessonNumber,
            SubjectName,
            RawTeachers,
            Classroom
            )
            VALUES
            (?,?,?,?,?)
            """,
            (
                item.GroupNumber,
                FormatNumber(
                    item.LessonNumber
                ),
                item.SubjectName,
                item.RawTeachers,
                item.Classroom
            )
        )
    connection.commit()
    connection.close()


def TeacherExists(teacher):
    connection = sqlite3.connect(
        DbPath
    )
    cursor = connection.cursor()
    cursor.execute(

        """
        SELECT COUNT(*)
        FROM Schedule
        WHERE RawTeachers LIKE ?

        """,

        (
            "%" + teacher + "%",
        )

    )

    count = cursor.fetchone()[0]

    connection.close()

    return count > 0


def GroupExists(GroupNumber):
    connection = sqlite3.connect(
        DbPath
    )

    cursor = connection.cursor()

    cursor.execute(

        """
        SELECT COUNT(*)
        FROM Schedule
        WHERE GroupNumber=?

        """,

        (
            GroupNumber,
        )

    )

    count = cursor.fetchone()[0]

    connection.close()

    return count > 0


def SaveTeacher(chatId, teacherName):
    connection = sqlite3.connect(
        DbPath
    )

    cursor = connection.cursor()

    cursor.execute(

        """

        INSERT INTO Users
        (
        ChatId,
        Role,
        Name
        )

        VALUES
        (
        ?,
        'teacher',
        ?
        )


        ON CONFLICT(ChatId)
        DO UPDATE SET

        Role='teacher',
        Name=?


        """,

        (

            chatId,

            teacherName,

            teacherName

        )

    )

    connection.commit()

    connection.close()


def SaveGroup(chatId, groupNumber):
    connection = sqlite3.connect(
        DbPath
    )

    cursor = connection.cursor()

    cursor.execute(

        """

        INSERT INTO Users
        (
        ChatId,
        Role,
        GroupNumber
        )


        VALUES
        (
        ?,
        'student',
        ?
        )


        ON CONFLICT(ChatId)

        DO UPDATE SET

        Role='student',

        GroupNumber=?

        """,

        (

            chatId,

            groupNumber,

            groupNumber

        )

    )

    connection.commit()

    connection.close()


def ShowScheduleStudent(chatId):
    with open(
            "date.txt",
            encoding="utf-8"
    ) as file:

        scheduleDate = file.read().strip()

    connection = sqlite3.connect(
        DbPath
    )

    cursor = connection.cursor()

    cursor.execute(

        """

        SELECT GroupNumber

        FROM Users

        WHERE ChatId=?

        """,

        (
            chatId,
        )

    )

    result = cursor.fetchone()

    if result is None:
        return "Группа не найдена"

    groupNumber = result[0]

    cursor.execute(

        """

        SELECT

        LessonNumber,
        SubjectName,
        RawTeachers,
        Classroom


        FROM Schedule


        WHERE GroupNumber=?


        """,

        (
            groupNumber,
        )

    )

    rows = cursor.fetchall()

    scheduleText = (

        f"Расписание группы {groupNumber}\n"

        f"на {scheduleDate}\n\n"

    )

    for row in rows:
        scheduleText += (

            f"Пара: {row[0]}\n"

            f"Предмет: {row[1]}\n"

            f"Преподаватель: {row[2]}\n"

            f"Кабинет: {row[3]}\n\n"

        )

    connection.close()

    return scheduleText


def ShowScheduleTeacher(chatId):
    with open(
            "date.txt",
            encoding="utf-8"
    ) as file:

        scheduleDate = file.read().strip()

    connection = sqlite3.connect(
        DbPath
    )

    cursor = connection.cursor()

    cursor.execute(

        """

        SELECT Name

        FROM Users

        WHERE ChatId=?

        """,

        (
            chatId,
        )

    )

    result = cursor.fetchone()

    if result is None:
        return "Преподаватель не найден"

    RawTeachers = result[0]

    cursor.execute(

        """

        SELECT

        LessonNumber,

        GroupNumber,

        SubjectName,

        Classroom


        FROM Schedule


        WHERE RawTeachers LIKE ?


        ORDER BY LessonNumber


        """,

        (

            "%" + RawTeachers + "%",

        )

    )

    rows = cursor.fetchall()

    scheduleText = (

        f"Расписание для преподавателя {RawTeachers}\n"

        f"на {scheduleDate}\n\n"

    )

    for row in rows:
        scheduleText += (

            f"Пара: {row[0]}\n"

            f"Группа: {row[1]}\n"

            f"Предмет: {row[2]}\n"

            f"Кабинет: {row[3]}\n\n"

        )

    connection.close()

    return scheduleText


def ParseScheduleDate(soup):
    title = soup.select_one(
        "h3.wpdt-c"
    )

    if title is None:
        return ""

    text = Normalize(
        title.text
    )

    match = re.search(
        r"\d{2}\.\d{2}\.\d{2}",
        text
    )

    if match:
        return match.group()

    return ""


async def CheckSubscription(userId):
    try:

        member = await bot.get_chat_member(

            ChannelUsername,

            userId

        )

        return member.status in [

            ChatMemberStatus.MEMBER,

            ChatMemberStatus.ADMINISTRATOR,

            ChatMemberStatus.CREATOR

        ]


    except:

        return False


def SubscribeKeyboard():
    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="📢 Подписаться",

                    url="https://t.me/ORSHAGAK"

                )

            ]

        ]

    )


def MainKeyboard():
    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="Преподаватель",

                    callback_data="teacher"

                ),

                InlineKeyboardButton(

                    text="Студент",

                    callback_data="student"

                )

            ]

        ]

    )


def ScheduleKeyboard(student=False):
    if student:

        show = "show_schedule_student"

    else:

        show = "show_schedule_teacher"

    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="Показать расписание",

                    callback_data=show

                )

            ],

            [

                InlineKeyboardButton(

                    text="Преподаватель",

                    callback_data="teacher"

                ),

                InlineKeyboardButton(

                    text="Студент",

                    callback_data="student"

                )

            ]

        ]

    )


@dp.message(Command("start"))
async def start(message: types.Message):
    userId = message.from_user.id

    if not await CheckSubscription(userId):
        await message.answer(

            "❌ Для использования бота нужно подписаться.",

            reply_markup=SubscribeKeyboard()

        )

        return

    await message.answer(

        "Выберите роль",

        reply_markup=MainKeyboard()

    )


@dp.callback_query()
async def callback_handler(call: types.CallbackQuery):
    userId = call.from_user.id

    if not await CheckSubscription(userId):
        await call.answer(

            "❌ Сначала подпишитесь на канал",

            show_alert=True

        )

        return

    if call.data == "teacher":

        userStates[userId] = "wait_teacher"

        await bot.send_message(

            userId,

            "Введите фамилию преподавателя\nНапример: Иванов"

        )





    elif call.data == "student":

        userStates[userId] = "wait_group"

        await bot.send_message(

            userId,

            "Введите номер группы"

        )






    elif call.data == "show_schedule_student":

        text = ShowScheduleStudent(

            userId

        )

        await bot.send_message(

            userId,

            text,

            reply_markup=ScheduleKeyboard(True)

        )





    elif call.data == "show_schedule_teacher":

        text = ShowScheduleTeacher(

            userId

        )

        await bot.send_message(

            userId,

            text,

            reply_markup=ScheduleKeyboard(False)

        )

    await call.answer()


@dp.message()
async def message_handler(message: types.Message):
    chatId = message.chat.id

    if chatId not in userStates:
        return

    state = userStates[chatId]

    if state == "wait_teacher":

        teacherName = message.text

        if TeacherExists(teacherName):

            SaveTeacher(

                chatId,

                teacherName

            )

            userStates.pop(

                chatId

            )

            await message.answer(

                f"Преподаватель сохранён:\n{teacherName}",

                reply_markup=ScheduleKeyboard()

            )



        else:

            await message.answer(

                "Преподаватель не найден или у него нет занятий"

            )






    elif state == "wait_group":

        groupNumber = message.text

        if GroupExists(groupNumber):

            SaveGroup(

                chatId,

                groupNumber

            )

            userStates.pop(

                chatId

            )

            await message.answer(

                f"Группа сохранена:\n{groupNumber}",

                reply_markup=ScheduleKeyboard(True)

            )



        else:

            await message.answer(

                f"Группа не найдена:\n{groupNumber}"

            )


async def UpdateSchedule():
    while True:

        try:

            await asyncio.sleep(

                3600

            )

            print(

                "Обновление расписания..."

            )

            records = await ParseScheduleAsync()

            SaveToDatabase(

                records

            )

            print(

                f"Расписание обновлено. Записей: {len(records)}"

            )



        except Exception as ex:

            print(

                "Ошибка обновления:",

                ex

            )


async def main():
    print(

        "Первичная загрузка расписания"

    )

    records = await ParseScheduleAsync()

    SaveToDatabase(

        records

    )

    print(

        f"Загружено: {len(records)}"

    )

    asyncio.create_task(

        UpdateSchedule()

    )

    print(

        "Бот запущен"

    )

    await dp.start_polling(

        bot

    )


if __name__ == "__main__":
    asyncio.run(

        main()

    )
