from datetime import date

ADULT_AGE_YEARS = 18


def age_on(date_of_birth: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if had_birthday else 1)


def is_adult_on(date_of_birth: date, today: date) -> bool:
    return age_on(date_of_birth, today) >= ADULT_AGE_YEARS
