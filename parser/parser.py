# parser_selenium.py  (или тоже parser.py, если выбираешь этот путь)

import os
import re
import logging
import urllib.parse
from time import sleep

from dotenv import load_dotenv
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from db import (
    init_db,
    SessionLocal,
    Category,
    PlaceCategory,
    SourceEnum,
    PlaceTypeEnum,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

load_dotenv()

URLS = {
    "concert": "https://afisha.yandex.ru/moscow/concert",
    "theatre": "https://afisha.yandex.ru/moscow/theatre",
    "art": "https://afisha.yandex.ru/moscow/art",
    "cinema": "https://afisha.yandex.ru/moscow/cinema",
    "excursions": "https://afisha.yandex.ru/moscow/excursions",
    "quest": "https://afisha.yandex.ru/moscow/quest",
}


# --------- утилиты ---------

def make_correct_url(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"(https?://\S+\.(?:jpg|jpeg|png|gif|webp))", url)
    return m.group(1) if m else None


def replace_illegal_characters(text):
    if isinstance(text, str):
        return "".join(ch if ch.isprintable() else " " for ch in text)
    return text


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if "description" in df.columns:
        df["description"] = df["description"].apply(replace_illegal_characters)
    return df


# --------- Selenium setup ---------

def create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    return driver


# --------- парсинг страницы ---------

def parse_list_page(driver: webdriver.Chrome, url: str, place_type: str) -> pd.DataFrame:
    logging.info(f"Парсим URL (Selenium): {url}")

    driver.get(url)
    # грубое ожидание загрузки; лучше заменить явным ожиданием нужного селектора
    sleep(5)

    # селектор зависит от реальной верстки.
    # если в DevTools у карточки есть data-test-id="eventCard-root",
    # можно использовать [data-test-id='eventCard-root'].
    cards = driver.find_elements(By.CSS_SELECTOR, "[data-test-id='eventCard-root']")
    if not cards:
        # запасной вариант — по классу, который ты видел (например, .kzFGcP или др.)
        cards = driver.find_elements(By.CSS_SELECTOR, "[data-event-id]")
    if not cards:
        logging.warning(f"Карточки мероприятий не найдены на {url}")
        return pd.DataFrame(columns=["name", "description", "image", "url", "type", "town"])

    items: list[dict] = []

    for card in cards:
        try:
            link = (
                card.find_element(By.CSS_SELECTOR, "[data-test-id='eventCard.link']")
                if card.find_elements(By.CSS_SELECTOR, "[data-test-id='eventCard.link']")
                else card.find_element(By.CSS_SELECTOR, "a[href]")
            )
        except NoSuchElementException:
            continue

        href = link.get_attribute("href")
        if not href:
            rel = link.get_attribute("href") or link.get_attribute("data-href")
            href = urllib.parse.urljoin("https://afisha.yandex.ru", rel)

        name = link.get_attribute("aria-label") or link.text.strip()
        if not name:
            continue

        img_url = None
        try:
            img_el = card.find_element(By.CSS_SELECTOR, "img")
            img_url = img_el.get_attribute("src") or img_el.get_attribute("srcset")
        except NoSuchElementException:
            pass

        items.append(
            {
                "name": name,
                "description": "",
                "image": img_url,
                "url": href,
                "type": place_type,
                "town": "Москва",
            }
        )

    df = pd.DataFrame(items)
    if df.empty:
        logging.warning(f"Не удалось собрать данные для {url}")
        return df

    df = (
        clean_df(df)
        .assign(image=lambda x: x["image"].apply(make_correct_url))
        .drop_duplicates(subset=["name", "type", "town"])
        .reset_index(drop=True)
    )
    return df


# --------- сохранение в БД ---------

def save_places_to_db(df: pd.DataFrame):
    from db import Place

    session = SessionLocal()
    try:
        src = session.get(SourceEnum, "yandex_afisha")
        if not src:
            src = SourceEnum(value="yandex_afisha")
            session.add(src)
            session.commit()

        for _, row in df.iterrows():
            place_type = row["type"]

            if not session.get(PlaceTypeEnum, place_type):
                session.add(PlaceTypeEnum(value=place_type))
                session.commit()

            category = session.query(Category).filter_by(name=place_type).one_or_none()
            if not category:
                category = Category(name=place_type)
                session.add(category)
                session.commit()

            existing = (
                session.query(Place)
                .filter_by(name=row["name"], source="yandex_afisha")
                .one_or_none()
            )
            if existing:
                continue

            place = Place(
                name=row["name"],
                description=row["description"],
                type=place_type,
                source="yandex_afisha",
            )
            session.add(place)
            session.flush()

            session.add(PlaceCategory(place_id=place.id, category_id=category.id))

        session.commit()
        logging.info("Мероприятия сохранены в БД (Selenium‑парсер)")
    except Exception as e:
        logging.error(f"Ошибка при сохранении: {e}")
        session.rollback()
        raise
    finally:
        session.close()


# --------- запуск ---------

def run_parser():
    init_db()

    driver = create_driver()
    try:
        all_data = pd.DataFrame()
        for place_type, url in URLS.items():
            df = parse_list_page(driver, url, place_type)
            all_data = pd.concat([all_data, df], ignore_index=True)

        if all_data.empty:
            logging.warning("Ничего не распарсилось (Selenium‑вариант)")
            return

        save_places_to_db(all_data)
    finally:
        driver.quit()


if __name__ == "__main__":
    run_parser()
