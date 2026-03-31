import datetime
import calendar
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def create_calendar(year=None, month=None):
    if year is None or month is None:
        now = datetime.datetime.now()
        year = now.year
        month = now.month
    
    keyboard = []
    
    # First row - Month and Year
    row = [InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="IGNORE")]
    keyboard.append(row)
    
    # Second row - Week Days
    row = []
    for day in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
        row.append(InlineKeyboardButton(day, callback_data="IGNORE"))
    keyboard.append(row)
    
    # Calendar rows - Days of month
    my_calendar = calendar.monthcalendar(year, month)
    for week in my_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
            else:
                row.append(InlineKeyboardButton(str(day), callback_data=f"CAL-DAY-{year}-{month}-{day}"))
        keyboard.append(row)
        
    # Last row - Buttons
    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
        
    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1
        
    row = [
        InlineKeyboardButton("< Prev", callback_data=f"CAL-PREV-{prev_year}-{prev_month}"),
        InlineKeyboardButton(" ", callback_data="IGNORE"),
        InlineKeyboardButton("Next >", callback_data=f"CAL-NEXT-{next_year}-{next_month}")
    ]
    keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Date Options", callback_data="BACK_DATE_OPTIONS"),
        InlineKeyboardButton("❌ Cancel", callback_data="CANCEL")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def process_calendar_selection(query):
    """
    Returns (completed, date_str, new_markup)
    """
    data = query.data
    if data == "IGNORE":
        return False, None, None
        
    if data.startswith("CAL-DAY"):
        _, _, year, month, day = data.split("-")
        return True, f"{year}-{int(month):02d}-{int(day):02d}", None
        
    if data.startswith("CAL-PREV") or data.startswith("CAL-NEXT"):
        _, _, year, month = data.split("-")
        return False, None, create_calendar(int(year), int(month))
        
    return False, None, None

def create_time_keyboard(hour=None, minute=None):
    keyboard = []
    
    if hour is None:
        # Show hours 0-23
        keyboard.append([InlineKeyboardButton("Select Hour", callback_data="IGNORE")])
        for i in range(0, 24, 4):
            row = []
            for j in range(4):
                h = i + j
                row.append(InlineKeyboardButton(f"{h:02d}:00", callback_data=f"TIME-HR-{h}"))
            keyboard.append(row)
    elif minute is None:
        # Show minutes 00, 05, 10... 55
        keyboard.append([InlineKeyboardButton(f"Hour: {hour:02d} - Select Minute", callback_data="IGNORE")])
        for i in range(0, 60, 15):
            row = []
            for j in range(0, 15, 5):
                m = i + j
                row.append(InlineKeyboardButton(f"{m:02d}", callback_data=f"TIME-MIN-{hour}-{m}"))
            keyboard.append(row)
            
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Calendar", callback_data="BACK_CALENDAR"),
        InlineKeyboardButton("❌ Cancel", callback_data="CANCEL")
    ])

    return InlineKeyboardMarkup(keyboard)

def process_time_selection(query):
    """
    Returns (completed, time_str, new_markup)
    """
    data = query.data
    if data == "IGNORE":
        return False, None, None
        
    if data.startswith("TIME-HR"):
        h = int(data.split("-")[2])
        return False, None, create_time_keyboard(hour=h)
        
    if data.startswith("TIME-MIN"):
        parts = data.split("-")
        h = int(parts[2])
        m = int(parts[3])
        return True, f"{h:02d}:{m:02d}", None
        
    return False, None, None
